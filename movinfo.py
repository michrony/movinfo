# Version: 02/13/2013 - initial creation
# Version: 02/18/2013 - introduced descriptor processing and CLI
# Version: 02/26/2013 - added items check
# Version: 03/08/2013 - added checking review links
# Version: 05/03/2013 - get Netflix info from freebase, Netflix API retired
# Version: 05/08/2013 - added rovi API
# Version: 04/17/2014 - descriptor format update, set desc file acc time to created
# Version: 05/09/2014 - append *dscj.txt if there is one
# Version: 05/12/2014 - introduced config file movinfo.json
#                       introduced netfgethtm to get Netflix info using html from Netflix dvd search 
# Version: 05/15/2014 - introduced comments removal by rmComments()

# Rotten Tomatoes API: https://secure.mashery.com/login/developer.rottentomatoes.com/
# Rovi Metadata and Search API: https://secure.mashery.com/login/developer.rovicorp.com/

import sys, os, datetime, httplib2, urllib, re, json, copy
import urllib2
import cookielib
import time, hashlib
from datetime import datetime
import argparse, glob
from sets import Set
import pprint, textwrap

help = '''
Create/update movie descriptor *.info.txt using info from Rotten Tomatoes, Netflix, IMDB/omdb, Rovi.
Movie descriptor includes json and plain ASCII parts, ASCII is built from json.
After descriptor is created with -n option, json part can be updates manually. 
Then ASCII part is compiled from json by -u option.
NOTE: Web service keys are kept in movinfo.json.
'''
#----------------------------------------------------------------------------------------------------
# all symbols after x'80' => HTML encoding $#xxx;
def utf8(latin1): 
# http://inamidst.com/stuff/2010/96.py
# http://www.ascii-code.com/
      #print "=>"
      Res = ""
      for character in latin1: 
         codepoint = ord(character)
         if codepoint < 0x80: Res = Res + character
         else: Res = "%s&#%d;" % (Res, codepoint) 

      return Res
#----------------------------------------------------------------------------------------------------
# Check if y1 from the response matches with y2 in the descriptor
# y1 can be int or string
# y2 can be int or list of ints: 2000 or [2000, 2005, 2010]
# y1 matches OK if abs(y1-y2)=0
def checkYear(y1, y2):

 try: y1 = int(y1)
 except: 
     return False 

 if (y2.__class__.__name__ != "list"):
     y2 = [y2]

 for y in y2:
    if (abs(y1-int(y))<=0): return True
 
 return False
#------------------------------------
def omdbget(IN):

 name  = IN["name"]
 year  = IN["year"]
 keys = ["urlimdb", "director", "synopsis", "name", "year"]
 N    = len(keys)
 for el in keys:
     if (el in IN): N = N-1
 if (N==0): return IN # all data already in IN

 REQ   = "http://www.omdbapi.com/?t=%s"
 myREQ = REQ % (urllib.quote(name))
 try: resp, res = httplib2.Http().request(myREQ)
 except: 
   print "omdbget: GET failed for %s" % (name)
   return IN

 try:
   res = json.loads(res)
 except: 
   print "omdbget: Wrong response for %s" % (name)
   return IN

 #pprint.pprint(res)
 if ("Error" in res or not checkYear(res["Year"], year)):
   print "omdbget: Not found %s" % (name)
   return IN 

 # results => OUT
 OUT = copy.deepcopy(IN)
 #pprint.pprint(res)
 if (not "urlimdb" in OUT and "imdbID" in res): OUT["urlimdb"]  = "http://www.imdb.com/title/" + res["imdbID"]
 if (not "director"  in OUT and "Director" in res):  OUT["director"] = res["Director"]
 if (not "synopsis" in OUT and "Plot" in res):  OUT["synopsis"] = res["Plot"]
 if (not "name" in OUT and "Title" in res):     OUT["name"]     = res["Title"]
 if (not "year" in OUT):                        OUT["year"]     = year

 return OUT
#----------------------------------------------------------------------------------------------------
def rovigetcast(IN):
 OUT = []
 for el in IN:
   OUT.append([utf8(el["name"]), utf8(el["role"])]) 
 return OUT
#----------------------------------------------------------------------------------------------------
# rovi docs: http://prod-doc.rovicorp.com/mashery/index.php/Media-recognition-api/v2/match 
# http://developer.rovicorp.com/io-docs
def roviget(IN):
 if (not "name" in IN or "year" not in IN or "idrovi" in IN): return IN

 # URL to get movieId, title, directors, cast, directors
 # then search the resultset by title, releaseYear
 api_url      = "http://api.rovicorp.com/recognition/v2.1/amgvideo/match/video?"
 api_url_parm = "entitytype=movie&title=%s&include=cast,synopsis&size=50&format=json&apikey=%s&sig=%s"

 # URL to get cast, synopsis by movieID
 api_url1 = "http://api.rovicorp.com/data/v1/movie/info?movieid=%s&include=cast,synopsis&format=json&apikey=%s&sig=%s"

 timestamp = int(time.time())
 m = hashlib.md5()
 m.update(cfg["ROVI_SEARCH_KEY"])
 m.update(cfg["ROVI_SEARCH_SECRET"])
 m.update(str(timestamp))
 SIG = m.hexdigest()

 api_url_parm = api_url_parm % (IN["name"], cfg["ROVI_SEARCH_KEY"], SIG)
 url = api_url + api_url_parm
 #url = urllib.quote(url)
 #print url
 try:    response = json.loads(urllib.urlopen(url).read())
 except: response = ""
 if (response=="" or "matchResponse" not in response or "results" not in response["matchResponse"]):
    print "roviget: Failed request"
    return IN
 #pprint.pprint(response)
 response = response["matchResponse"]["results"]
 if (response==None):
    print "roviget: Failed request"
    return IN
 id       = ""
 cast     = ""
 director = ""
 synopsys = ""
 itemsChecked = Set()
 for item in response:
   if (not "movie" in item): continue
   item = item["movie"]
   itemsChecked.add(utf8(item["title"]) + " - " + str(item["releaseYear"]))
   if (item["title"].lower()!=IN["name"].lower()): continue
   if (not checkYear(item["releaseYear"], IN["year"])): 
       print "rovget: Wrong year %s" % (item["releaseYear"])
       return IN
   id = [item["ids"]["cosmoId"], item["ids"]["movieId"]]
   cast = rovigetcast(item["cast"])
   for el in item["directors"]:
     director = ", " + el["name"]
   director = director[2:]
   try:         
      synopsis = "%s - By %s" % (item["synopsis"]["text"], item["synopsis"]["author"])
   except:
      synopsis = ""
   synopsis = synopsis.replace("[", "<") # get rid of [...] elements
   synopsis = synopsis.replace("]", ">")
   p = re.compile("<[^>]+>")
   synopsis = re.sub(p, "", synopsis)
   break

 if (id==""):
    itemsChecked = list(itemsChecked)
    itemsChecked.sort()
    print "rovget: Nothing found. Checked: %s" % (str(itemsChecked))
    return IN
 
 IN["idrovi"] = copy.deepcopy(id)

 lcast = 0
 if ("cast" in IN):    lcast = len(IN["cast"])
 if (len(cast)>lcast): IN["cast"] = copy.deepcopy(cast)

 ldir = 0
 if ("director" in IN):   ldir = len(IN["director"])
 if (len(director)>ldir): IN["director"] = director

 lsyn = 0
 if ("synopsis" in IN):   ldir = len(IN["synopsis"])
 if (len(synopsis)>lsyn): IN["synopsis"] = synopsis

 return IN
#----------------------------------------------------------------------------------------------------
# get Netflix URL using html from Netflix search
def netfgethtm(IN):

 years = IN["year"]
 if (years.__class__.__name__ != "list"):
     years = [years]
 for y in years:
     if ("urlnetf" in IN): return IN
     IN["year"] = int(y)
     IN = netfgethtm_(IN)

 return IN
#----------------------------------------------------------------------------------------------------
def netfgethtm_(IN):

 parm = ("%s %d" %(IN["name"], IN["year"])).replace(" ", "+")
 req  = "http://dvd.netflix.com/Search?v1=" + parm

 resp = ""
 try: 
      jar = cookielib.FileCookieJar("cookies") # allow Netflix cookies
      opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))
      resp = opener.open(req).read()
 except Exception, e:
      print "netfgethtm: GET failed " + str(e.args)
      return IN

 # split response to <li> items 
 resp = resp.split("<li style=") 
 resp.pop(0)
 last = resp[-1].split("</ol>")[0]
 resp[-1] = last
 
 found = ""
 for el in resp:
    #print textwrap.fill(el, 60)
    el_ = el.lower()
    if (el_.find(IN["name"].lower())<0): continue
    year = el.split("<span class=\"year\">")[1]
    year = int(year.split("</span")[0]) 
    if (year != IN["year"]): 
       print "netfgethtm: searching for %d, %d is rejected" % (IN["year"], year)
       #print textwrap.fill(el, 60)
       continue 

    print "netfgethtm: searching for %d, found %d" % (IN["year"], IN["year"])
    found = el
    break
 if (found==""):
    print "netfgethtm: nothing found for " + req
    return IN 
 
 #print textwrap.fill(found, 60)
 found = found.split("<a href=\"")[1]
 found = found.split("?")[0]
 IN["urlnetf"] = found
 
 return IN
#----------------------------------------------------------------------------------------------------
# get Netflix URL, director from freebase by IMDB URL
# https://developers.google.com/freebase/v1/mql-overview#querying-for-id-and-name
def netfget(IN):
 if ("urlimdb" not in IN or IN["urlimdb"] =="" or "urlnetf" in IN): return IN

 imdb_id = IN["urlimdb"].replace("http://www.imdb.com/name/", "")

 query = [{
   "type": "/film/film",
   "imdb_id":     imdb_id,
   "directed_by": None,
   "netflix_id":  None  
 }]
 params = {
           'query': json.dumps(query)
 }
 url = 'https://www.googleapis.com/freebase/v1/mqlread/?' + urllib.urlencode(params)
 response = json.loads(urllib.urlopen(url).read())
 urlnetfid = ""
 urlnetf   = ""
 director  = ""
 if ("result" in response and len(response["result"])>0 and "netflix_id" in response["result"][0]): 
    urlnetfid = response["result"][0]["netflix_id"]
    urlnetf   = "http://movies.netflix.com/Movie/" + urlnetfid
    director  = response["result"][0]["directed_by"]
 else: 
    print "netfget: Nothing for %s" % (imdb_id)
    return IN

 if (urlnetf!=""):          IN["urlnetf"]  = urlnetf
 if (not "director" in IN): IN["director"] = director
 #print response

 return IN
#----------------------------------------------------------------------------------------------------
def rottgetcast(IN):
 OUT = []
 for el in IN:
   if ("characters" in el): OUT.append([el["name"], el["characters"][0]])
   else:                    OUT.append([el["name"], ""]) 
 return OUT
#----------------------------------------------------------------------------------------------------
# See http://developer.rottentomatoes.com/docs/read/json/v10/Movie_Reviews
def rottgetreviews(ID, ROTT_API_KEY):
 OUT = []
 # get movie reviews by movie id
 REQ   = "http://api.rottentomatoes.com/api/public/v1.0/movies/%s/reviews.json?review_type=top_critic&apikey=%s"
 myREQ = REQ % (ID, ROTT_API_KEY)
 try: 
   resp, reviews = httplib2.Http().request(myREQ)
 except: 
   print "rottgetreviews: GET failed"
   return OUT
 try: 
   reviews = json.loads(reviews)
   reviews = reviews["reviews"]
 except: 
   print "rottgetreviews: Wrong response"
   return OUT
 
 if (len(reviews)==0): return OUT
 for el in reviews:
     if ("links" in el and "review" in el["links"]): 
        lnk = el["links"]["review"]
        lnk = lnk.replace("partner=Rotten Tomatoes", "")   
        OUT.append([el["critic"], lnk])

 return OUT
#----------------------------------------------------------------------------------------------------
# See http://developer.rottentomatoes.com/docs
def rottget(IN):
 if ("idrott" in IN): return IN

 name  = IN["name"]
 year  = IN["year"]
 REQ   = "http://api.rottentomatoes.com/api/public/v1.0/movies.json?apikey=%s&q=%s"

 # get movie id by movie name, 
 myREQ = REQ % (cfg["ROTT_API_KEY"], urllib.quote(name))
 #print myREQ 
 try: resp, res = httplib2.Http().request(myREQ)
 except: 
      print "rottget: GET failed for %s" % (name)
      return IN

 try: 
   res  = json.loads(res)
   res  = res["movies"]
   #pprint.pprint(res)
 except: 
   print "rottget: Wrong response for %s" % (name)
   return IN

 if (len(res)==0): 
    print "rottget: Not found %s" % (name)
    return IN

 for curr in res:
    #print curr["title"]
    if (checkYear(curr["year"], year)):
      break

 if (not checkYear(curr["year"], year)): 
    print "rottget: Wrong year %s - %s" % (name, curr["year"])
    return IN
 
 # get movie info including director by movie id
 REQ   = "http://api.rottentomatoes.com/api/public/v1.0/movies/%s.json?apikey=%s"
 myREQ = REQ % (curr["id"], cfg["ROTT_API_KEY"])
 resp, res = httplib2.Http().request(myREQ)
 res = json.loads(res)
 #print "=>" + res["title"]
 #pprint.pprint(res)

 try:    director = res["abridged_directors"][0]["name"]
 except: director = ""
 if ("name" in res):  name  = res["title"]
 else:                name  = ""
 if ("year" in res):  year  = res["year"]
 else:                year  = ""
 if ("id" in res):    id    = res["id"]
 else:                id    = ""
 if ("synopsis" in res): synopsis = res["synopsis"]
 else:                   synopsis = ""
 #print synopsis
 try:    urlrott = res["links"]["alternate"]
 except: urlrott = ""
 try:    urlimdb = "http://www.imdb.com/title/tt" + res["alternate_ids"]["imdb"]
 except: urlimdb = ""
 
 # results => OUT
 OUT = copy.deepcopy(IN)
 if ("abridged_cast" in res and len(res["abridged_cast"])>0):
    OUT["cast"] = copy.deepcopy(rottgetcast(res["abridged_cast"]))
 reviews = rottgetreviews(id, cfg["ROTT_API_KEY"])
 if (len(reviews)>0): OUT["urlrev"] = copy.deepcopy(reviews)
 if (not "director" in OUT and director!=""): OUT["director"] = director
 if (not "synopsis" in OUT and synopsis!=""): OUT["synopsis"] = synopsis
 if (not "name" in OUT and name!=""):         OUT["name"]     = name
 if (not "year" in OUT and year!=""):         OUT["year"]     = year
 if (not "urlimdb" in OUT and urlimdb!=""):   OUT["urlimdb"]  = urlimdb
 if (urlrott!=""):                            OUT["urlrott"]  = urlrott
 if (id!=""):                                 OUT["idrott"]   = id

 return OUT
#----------------------------------------------------------------------------------------------------
# Remove items in IN["urlrev"] with unresolved links
def checkLinks(IN):

 if (not "urlrev" in IN): return IN
 rm  = []
 OUT = []
 for el in IN["urlrev"]:
    try: resp, res = httplib2.Http().request(el[1])
    except: resp = {}
    if (not "status" in resp): resp["status"] = ""
    if (str(resp["status"])!="200"):
        rm.append(str(el))
        print "movinfo: removed %s %s status=%s" % (el[0], el[1], resp["status"])
    else: OUT.append(el)

 IN["urlrev"] = copy.deepcopy(OUT)

 if (len(rm)>0): 
    tmp = []
    if ("urlrevrm" in IN): tmp = IN["urlrevrm"]
    tmp = tmp + rm
    tmp = list(Set(tmp))
    IN["urlrevrm"] = tmp
 return IN
#----------------------------------------------------------------------------------------------------
# Check that certain entries are in IN and have proper format
def checkEntries(IN, new):

 unfilled = []
 for el in ["urlnetf", "urlrott", "idrovi"]:
    if (not el in IN): 
       unfilled.append(el)
     
 OK = True
 # Check that these are lists of [string, string] pairs
 for el in ["urlwik", "urlyou", "urlrev", "cast"]:
    if (not el in IN): 
       unfilled.append(el)
       continue
    if (not IN[el].__class__.__name__=="list"):
       print "movinfo.checkEntries: Wrong %s" % (el)
       pprint.pprint(In[el])
       OK = False
       continue
    for el_ in IN[el]:
        if (not el_.__class__.__name__=="list"):
           print "movinfo.checkEntries: Wrong %s" % (el)
           pprint.pprint(el_)
           OK = False
           continue
        if (not len(el_)==2 or el_[0].__class__.__name__!="str" or el_[1].__class__.__name__!="str"):
           print "movinfo.checkEntries: Wrong %s" % (el)
           pprint.pprint(el_)
           OK = False
           continue

 unfilled.sort()
 if (len(unfilled)>0 and not new): print "movinfo: Warning. Missing/wrong entries %s" % (unfilled) 

 return OK
#----------------------------------------------------------------------------------------------------
# remove commented entries ["#xxx", "yyy"]
def rmComments(IN):

 for el in IN.keys(): # remove commented entries of the 1st level
     if (el!="" and el[0]=="#"): del IN[el]
      
 for el in ["cast", "urlwik", "urlrev"]:
     if el not in IN: continue   
     out = []
     comm = False
     for item in IN[el]:
        if (item[0]!="" and item[0][0]=="#"): comm = True
        if (item[0]=="" or item[0][0]!="#"):  out.append(item)
      
     if (not comm): continue
     if (len(out)==0): 
        del IN[el]
        continue  
     IN[el] = out 

 return IN
#----------------------------------------------------------------------------------------------------
# Descriptor in the file fname => IN dictionary
def getDesc(fname, new):

 try:
   F   = open(fname)
   F_  = " " + F.read() + " "
   # get json descriptor
   if ("<!--info" in F_): 
      F_  = F_.split("<!--info")
      if ("-->" in F_[1]): F_ = F_[1].split("-->")
      else:                F_ = F_[1].split("->")
   else: F_ = [F_]
   IN  = json.loads(F_[0])
   F.close()
   #print IN
   #exit
 except:
   print "movinfo: Wrong JSON in %s" % fname
   return {}
 if (not "name" in IN or not "year" in IN):
   print "movinfo: No movie name/year in %s" % fname
   return {}
 
 OK = checkEntries(IN, new)
 if (not OK): return []
 if (not new): IN = rmComments(IN)

 return IN
#----------------------------------------------------------------------------------------------------
# <a *>X</a> => X
def procAtag(IN):
 if (IN.find("<a ")<0): return IN

 p  = re.compile("<a [^>]+>")
 IN = p.sub("", IN)
 IN = IN.replace("</a>", "")

 return IN
#----------------------------------------------------------------------------------------------------
def putDesc(fname, IN):

 INkeys = Set(IN.keys())

 HeaderYear = IN["year"]
 if (HeaderYear.__class__.__name__ == "list"): HeaderYear = HeaderYear[0]
 Header = "%s (%s)" % (IN["name"], HeaderYear)
 INkeys = INkeys - Set(["name", "year"])

 dir = "" # director
 if ("director" in IN): dir = "<b>Director:</b> %s\n" % (IN["director"])
 INkeys = INkeys - Set(["director"])

 syn = "" # synopsis
 if ("synopsis" in IN): syn = "<b>Synopis:</b> %s\n" % (IN["synopsis"])
 syn = procAtag(syn)
 INkeys = INkeys - Set(["synopsis"])

 rott = "" # Rotten link
 if ("urlrott" in IN): rott = IN["urlrott"] + "\n"
 INkeys = INkeys - Set(["urlrott"])

 netf = "" # Netflix link
 if ("urlnetf" in IN and IN["urlnetf"]!=""): netf = IN["urlnetf"] + "\n"
 INkeys = INkeys - Set(["urlnetf"])

 imdb = "" # IMDB link
 if ("urlimdb" in IN): imdb = IN["urlimdb"]
 INkeys = INkeys - Set(["urlimdb"])

 cast = ""
 if ("cast" in IN and len(IN["cast"])>0):
    for el in IN["cast"]:
        cast = cast + el[0] 
        if (el[1]!=""): cast = cast + " as " + el[1] + ", "
        else:           cast = cast + ", "
    cast = "<b>Cast:</b> %s\n" % (cast[0:len(cast)-2])
 INkeys = INkeys - Set(["cast"])

 rev = "" # reviews links
 if ("urlrev" in IN and len(IN["urlrev"])>0):
    for el in IN["urlrev"]:
        #print el
        if (len(el[0])>0): rev = "%s%s: %s\n" % (rev, el[0], el[1])
        else:              rev = "%s%s\n" % (rev, el[1])
 INkeys = INkeys - Set(["urlrev"])

 wik= "" # wiki links
 if ("urlwik" in IN and len(IN["urlwik"])>0):
    if (IN["urlwik"].__class__.__name__ == "str"): IN["urlwik"] = [["Wiki", IN["urlwik"]]] 
    for el in IN["urlwik"]:
        if (len(el[0])>0): wik = "%s%s: %s\n" % (wik, el[0], el[1])
        else:              wik = "%s%s\n" % (wik, el[1])
 INkeys = INkeys - Set(["urlwik"])

 you = "" # youtube links
 if ("urlyou" in IN and len(IN["urlyou"])>0):
    if (IN["urlyou"].__class__.__name__ == "str"): IN["urlyou"] = [["Youtube", IN["urlyou"]]] 
    for el in IN["urlyou"]:
        if (len(el[0])>0 and not el[0].startswith("Youtube")): el[0] = "Youtube. " + el[0]
        if (len(el[0])>0): you = "%s%s: %s\n" % (you, el[0], el[1])
        else:              you = "%s%s\n" % (you, el[1])
 INkeys = INkeys - Set(["urlyou"])

 IN_ = "<!-%s %s %s->\n" % (IN["created"], Header, imdb.replace("http://", "")) 
 IN_ = IN_ + dir + syn + cast + "<b>Links</b>\n" + wik + rott + netf + rev + you
 IN_ = IN_ + "<!--info\n%s-->\n" % (json.dumps(IN, indent=1))

 # append *dscj.txt if there is one
 fdscj = fname.replace("info.txt", "dscj.txt")
 if (os.path.exists(fdscj)):
    try: 
     F   = open(fdscj)
     IN_ = IN_ + F.read()
    except Exception, err: pass

 # write the prepared descriptor to *info.txt
 F   = open(fname, "w")
 codecFail = False
 try: F.write(IN_)
 except Exception, err:
   codecFail = str(err).find("can't encode character")>0 
 if (codecFail):  
    F.write(utf8(IN_)) 
 F.close()

 # set access time to created
 cr = IN["created"].split("-")
 if len(cr)>0:
    [y, m, d] = [int(cr[0]), int(cr[1]), int(cr[2])]
    t = datetime(y, m, d)
    t = time.mktime(t.timetuple())
    os.utime(fname, (t, t))

 # Check unusable entries
 unused = list(INkeys - Set(["idrott", "idrovi", "created", "urlrevrm"]))
 if (len(unused)>0):   print "movinfo: Warning. Unusable entries %s" % (unused) 
 if ("created" in IN): print "movinfo: Created %s\n" % (IN["created"])

 return
#----------------------------------------------------------------------------------------------------
# if newDesc=True,  create new Movie Descriptor using info from Rotten Tomatoes, Netflix, IMDB/omdb
# if newDesc=False, update Movie Descriptor using its updated json Descriptor 
def procDesc(fname, newDesc, linkCheck):
 
 Res = getDesc(fname, new)
 if (not "name" in Res or not "year" in Res): return
 name = Res["name"]
 year = Res["year"]
 if (newDesc):
    if (not "created" in Res):
       now = time
       Res["created"] = now.strftime("%Y-%m-%d")
    Res = rottget(Res)
    Res = omdbget(Res)
    Res = netfgethtm(Res)
    Res = netfget(Res)
    Res = roviget(Res)
 else: Res = netfget(netfgethtm(Res)) # try to add Netflix info to older descriptors
    
 if (linkCheck): Res = checkLinks(Res)
 putDesc(fname, Res)

 return
#----------------------------------------------------------------------------------------------------
cfg = {} 
def getCfg():
  
  global cfg
 
  fn = os.path.dirname(sys.argv[0]).replace("\\", "/") + "/movinfo.json"
  if (not os.path.exists(fn)):
       print "movinfo: %s does not exist" % (fn)  
       exit()
  try:
       cfg = json.loads(open(fn).read())
  except Exception, e:
       print "movinfo: wrong JSON in %s" % (fn)
       exit() 
  print "movinfo: use %s\n" % (fn)

  #print cfg
  issues = []
  if ("ROTT_API_KEY" not in cfg):       issues.append("ROTT_API_KEY")
  if ("ROVI_SEARCH_KEY" not in cfg):    issues.append("ROVI_SEARCH_KEY")
  if ("ROVI_SEARCH_SECRET" not in cfg): issues.append("ROVI_SEARCH_SECRET")
  if (len(issues)>0):
      print "movinfo: missing %s" % (str(issues))
      exit()
 
  return
#----------------------------------------------------------------------------------------------------

parser = argparse.ArgumentParser(description=help)
group  = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-n', action="store_true", help="Create new descriptor(s) using DB info with 'name', 'year' as movie seach arguments")
group.add_argument('-u', action="store_true", help="Update existing")
parser.add_argument("-l", action="store_true", help="Check links for reviews")
parser.add_argument("path", type = str, help="Movie Descriptor(s) to process")
args      = vars(parser.parse_args())
new       = args["n"]
linkCheck = args["l"]

getCfg()

fname = args["path"]
#print "movinfo: %s new=%s" % (fname, new)
if (fname.find("*")<0 and fname.endswith(".info.txt") and os.path.exists(fname)):
   procDesc(fname, new) 
   exit() 

List = glob.glob(args["path"])
List = [el for el in List if (el.endswith(".info.txt"))] # use only *.info.txt files
if (len(List)==0):
   print "movinfo: Nothing to process"
   exit()

for el in List:
   print "movinfo: %s new=%s" % (el, new)
   procDesc(el, new, linkCheck) 

exit()
