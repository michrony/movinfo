#!/usr/bin/python

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
# Version: 05/15/2014 - introduced removal of #-commented entries by rmComments()
# Version: 06/08/2014 - introduced -n with removing and replacing of old entries
# Version: 12/08/2014 - fixed rovigetcast bug
# Version: 09/13/2015 - reworked netfgethtm using beatifulsoup and xmltodict
# Version: 07/30/2017 - added -ue. Now -ue produces envelope around json desc in *.info.txt
#                       To simplify correcting JSON syntax, -n, -u produce pure JSON in *.info.txt
# Version: 08/13/2017 - added OMDB API key
# Version: 12/25/2017 - minor fix of checkEntries
# Version: 06/03/2018 - minor fix to enable https://imdb.com
# Version: 06/25/2018 - added placeholders to missing keys
# Version: 07/07/2018 - removed all about Netflix, Rotten APIs
# Version: 08/06/2018 - path argument retired
#                       added setDesc() to use pre-existing *.info.txt or create a new one
#                       create empty *dscj.txt if it does not exist
# Version: 12/02/2018 - exception procs in roviget()
# Version: 12/17/2018 - updated utf8()
# Version: 12/15/2019 - updated utf8()
# Version: 01/12/2020 - now works both in Python 2.7 and 3.8.0
#                       roviget() changed to use http2
#                       utf8() updated 

# Rovi Metadata and Search API: https://secure.mashery.com/login/developer.rovicorp.com/
# OMDB API: http://www.omdbapi.com/ https://www.patreon.com/bePatron?c=740003

import sys, os, platform, datetime, re, json, copy
import shutil
import time, hashlib
from datetime import datetime
import argparse, glob, pprint
from builtins import str

import httplib2

try:
    from urllib import quote        # Python 2.X
except ImportError:
    from urllib.parse import quote  # Python 3+ 

# For Win/ActivePython, CentOS run:
# pip install httplib2

help = '''
Create/update movie descriptor *.info.txt using info from Rotten Tomatoes, IMDB/omdb, Rovi.
Movie descriptor includes json and ASCII envelop, envelope is built from json.
After descriptor is created with -n option, json part can be updated manually. 
Then ASCII envelope is compiled from json by -ue option.
NOTE: Web service keys are kept in movinfo.json.
'''
#----------------------------------------------------------------------------------------------------
# all symbols after x'80' => HTML encoding $#xxx;
def utf8(str): 
    if (hasattr(str, "decode")): return str.decode('utf-8').encode('ascii', 'xmlcharrefreplace')
    else: return str.encode('ascii', 'xmlcharrefreplace').decode('utf-8')
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

 REQ   = "http://www.omdbapi.com/?t=%s&apikey=%s"
 myREQ = REQ % (quote(name), cfg["OMDB_API_KEY"])
 try: resp, res = httplib2.Http().request(myREQ)
 except: 
   print ("omdbget(): GET failed for %s" % (name))
   return IN

 try:
   res = json.loads(res)
 except: 
   print ("omdbget(): Wrong response for %s" % (name))
   return IN

 #pprint.pprint(res)
 if ("Error" in res or not checkYear(res["Year"], year)):
   print ("omdbget(): Not found %s" % (name))
   return IN 

 actors = []
 if ("Actors" in res):
   actors_ = res["Actors"].split(", ")
   for el in actors_: actors.append([el, ""])
   
 # results => OUT
 OUT = copy.deepcopy(IN)
 #pprint.pprint(res)
 if (not "urlimdb" in OUT and "imdbID" in res): OUT["urlimdb"]  = "http://www.imdb.com/title/" + res["imdbID"]
 if (not "director"  in OUT and "Director" in res):  OUT["director"] = res["Director"]
 if (not "synopsis" in OUT and "Plot" in res):  OUT["synopsis"] = res["Plot"]
 if (not "name" in OUT and "Title" in res):     OUT["name"]     = res["Title"]
 if (not "year" in OUT):                        OUT["year"]     = year
 if (not "cast" in OUT):                        OUT["cast"]     = actors

 #pprint.pprint(res) 
 print ("omdbget(): OK")
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

 # URL to get cast, synopsis by movieID
 apiUrlId = "http://api.rovicorp.com/data/v1/movie/info?movieid=%s&include=cast,synopsis&format=json&apikey=%s&sig=%s"
 # URL to get movieId, title, directors, cast, directors
 # then search the resultset by title, releaseYear
 apiUrl   = "http://api.rovicorp.com/recognition/v2.1/amgvideo/match/video?"

 apiParmFmt = "entitytype=movie&title=%s&include=cast,synopsis&size=50&format=json&apikey=%s&sig=%s"

 timestamp = int(time.time())
 m = hashlib.md5()
 m.update(cfg["ROVI_SEARCH_KEY"].encode("utf-8"))
 m.update(cfg["ROVI_SEARCH_SECRET"].encode("utf-8"))
 m.update(str(timestamp).encode("utf-8"))
 SIG = m.hexdigest()

 apiParm = apiParmFmt % (quote(IN["name"]), cfg["ROVI_SEARCH_KEY"], SIG)
 url = (apiUrl + apiParm)
 
 try: resp, res = httplib2.Http().request(url)
 except Exception as err:
   print ("roviget(): GET failed: " + str(err))
   return IN
 res = utf8(res)
 
 try:
   response = json.loads(res)
 except Exception as err:
   print ("roviget(): Wrong response: " + str(err))
   return IN
 
 if ("matchResponse" not in response or "results" not in response["matchResponse"]):
    print ("roviget: wrong response")
    return IN
 #pprint.pprint(response)
 response = response["matchResponse"]["results"]
 if (response==None):
    print ("roviget: Failed request")
    return IN
 id       = ""
 cast     = ""
 director = ""
 synopsys = ""
 itemsChecked = set()
 for item in response:
   if (not "movie" in item): continue
   item = item["movie"]
   itemsChecked.add(utf8(item["title"]) + " - " + str(item["releaseYear"]))
   if (item["title"].lower()!=IN["name"].lower()): continue
   if (not checkYear(item["releaseYear"], IN["year"])): 
       print ("roviget(): Wrong year %s" % (item["releaseYear"]))
       return IN
   id = [item["ids"]["cosmoId"], item["ids"]["movieId"]]
   try: 
     for el in item["directors"]:
        director = ", " + el["name"]
     director = director[2:]
   except Exception as err: 
     print ("roviget(): Can't process director " + str(err))
   try:         
      cast = rovigetcast(item["cast"])
   except:
      cast = []
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
    print ("roviget(): Nothing found. Checked: %s" % (str(itemsChecked)))
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

 print ("roviget(): OK")
 return IN
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
        print ("movinfo: removed %s %s status=%s" % (el[0], el[1], resp["status"]))
    else: OUT.append(el)

 IN["urlrev"] = copy.deepcopy(OUT)

 if (len(rm)>0): 
    tmp = []
    if ("urlrevrm" in IN): tmp = IN["urlrevrm"]
    tmp = tmp + rm
    tmp = list(set(tmp))
    IN["urlrevrm"] = tmp
 return IN
#----------------------------------------------------------------------------------------------------
# Check that certain entries are in IN and have proper format
def checkEntries(IN, new):

 if (new):
    allowed = set(["created", "year", "name", "urlwik", "urlimdb", "urlrev"])
    present = set(list(IN.keys()))
    extras  = present - allowed
    if (len(extras)>0):
       extras = list(extras)
       extras.sort() 
       print ("checkEntries(): entries not allowed for new and removed")
       pprint.pprint(extras)
       for el in extras: del IN[el]
           
 unfilled = []
 for el in ["idrovi"]:
    if (not el in IN): 
       unfilled.append(el)
     
 OK = True
 # Check that these are lists of [string, string] pairs
 for el in ["urlwik", "urlyou", "urlrev", "cast"]:
    if (not el in IN): 
       IN[el] = copy.deepcopy([  
           ["", ""], ["", ""], ["", ""]
       ])
       continue
    if (not IN[el].__class__.__name__=="list"):
       print ("movinfo.checkEntries: Wrong %s" % (el))
       #pprint.pprint(In[el])
       OK = False
       continue
    for el_ in IN[el]:
        if (not el_.__class__.__name__=="list"):
           print ("movinfo.checkEntries: Wrong %s" % (el))
           pprint.pprint(el_)
           OK = False
           continue
        str = el_[0].__class__.__name__=="str" or el_[0].__class__.__name__=="unicode"
        str = str and (el_[1].__class__.__name__=="str" or el_[1].__class__.__name__=="unicode") 
        if (len(el_)!=2 or not str):
           #print el_[0].__class__.__name__
           print ("movinfo.checkEntries: Wrong %s" % (el))
           pprint.pprint(el_)
           OK = False
           continue

 unfilled.sort()
 if (len(unfilled)>0 and not new): print ("movinfo: Warning. Missing/wrong entries %s" % (unfilled)) 

 return [OK, IN]
#----------------------------------------------------------------------------------------------------
# remove commented entries ["#xxx", "yyy"]
def rmComments(IN):

 for el in list(IN.keys()): # remove commented entries of the 1st level
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
   F_  = utf8(F_)
   # get json descriptor
   if ("<!--info" in F_): 
      F_  = F_.split("<!--info")
      if ("-->" in F_[1]): F_ = F_[1].split("-->")
      else:                F_ = F_[1].split("->")
   else: F_ = [F_]
   IN  = json.loads(F_[0])
   F.close()
   #print (IN)
   #exit
 except:
   print ("movinfo: Wrong JSON in %s" % fname)
   return {}
 if (not "name" in IN or not "year" in IN):
   print ("movinfo: No movie name/year in %s" % fname)
   return {}
 
 [OK, IN] = checkEntries(IN, new)
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
def putDesc(fname, IN, env):

 INkeys = set(list(IN.keys()))

 HeaderYear = IN["year"]
 if (HeaderYear.__class__.__name__ == "list"): HeaderYear = HeaderYear[0]
 Header = "%s (%s)" % (IN["name"], HeaderYear)
 INkeys = INkeys - set(["name", "year"])

 dir = "" # director
 if ("director" in IN): dir = "<b>Director:</b> %s\n" % (IN["director"])
 INkeys = INkeys - set(["director"])

 syn = "" # synopsis
 if ("synopsis" in IN): syn = "<b>Synopsis:</b> %s\n" % (IN["synopsis"])
 syn = procAtag(syn)
 INkeys = INkeys - set(["synopsis"])

 imdb = "" # IMDB link
 if ("urlimdb" in IN): imdb = IN["urlimdb"]
 INkeys = INkeys - set(["urlimdb"])

 cast = ""
 if ("cast" in IN and len(IN["cast"])>0):
    for el in IN["cast"]:
        cast = cast + el[0] 
        if (el[1]!=""): cast = cast + " as <b>" + el[1] + "</b>, "
        else:           cast = cast + ", "
    cast = "<b>Cast:</b> %s\n" % (cast[0:len(cast)-2])
 INkeys = INkeys - set(["cast"])

 rev = "" # reviews links
 if ("urlrev" in IN and len(IN["urlrev"])>0):
    for el in IN["urlrev"]:
        #print (el)
        if (len(el[0])>0): rev = "%s%s: %s\n" % (rev, el[0], el[1])
        else:              rev = "%s%s\n" % (rev, el[1])
 rev = rev.strip()       
 if (rev!=""): rev = rev + "\n"

 INkeys = INkeys - set(["urlrev"])

 wik = "" # wiki links
 if ("urlwik" in IN and len(IN["urlwik"])>0):
    if (IN["urlwik"].__class__.__name__ == "str"): IN["urlwik"] = [["Wiki", IN["urlwik"]]] 
    for el in IN["urlwik"]:
        if (len(el[0])>0):   wik = "%s%s: %s\n" % (wik, el[0], el[1])
        elif (len(el[1])>0): wik = "%sWiki: %s\n" % (wik, el[1])
#       else:              wik = "%s%s\n % (wik, el[1])

 INkeys = INkeys - set(["urlwik"])

 you = "" # youtube links
 if ("urlyou" in IN and len(IN["urlyou"])>0):
    if (IN["urlyou"].__class__.__name__ == "str"): IN["urlyou"] = [["Youtube", IN["urlyou"]]] 
    for el in IN["urlyou"]:
        if (len(el[0])>0 and not el[0].startswith("Youtube")): el[0] = "Youtube. " + el[0]
        if (len(el[0])>0): you = "%s%s: %s\n" % (you, el[0], el[1])
        else:              you = "%s%s\n" % (you, el[1])
 you = you.strip()       
 if (you!=""): you = you + "\n"
 
 INkeys = INkeys - set(["urlyou"])

 if ("created" not in IN): IN["created"] = ""
 
 print ("putDesc(): env=" + str(env))
 if (env): 
    _imdb = imdb.replace("http://", "")
    _imdb = _imdb.replace("https://", "")
    IN_ = "<!-%s %s %s->\n" % (IN["created"], Header, _imdb) 
    IN_ = IN_ + dir + syn + cast + "<b>Links</b>\n" + wik + rev + you
    IN_ = IN_ + "<!--info\n%s-->\n" % (json.dumps(IN, indent=1))
 else:  
    IN_ = json.dumps(IN, indent=1)

 #print IN_
 
 # append *dscj.txt if there is one
 fdscj = fname.replace("info.txt", "dscj.txt")
 if (env and os.path.exists(fdscj)):
    try: 
     F   = open(fdscj)
     F_  = F.read()
     if ("<!--dscj" in F_):
        IN_ = IN_ + F_
        print ("putDesc(): Appended " + fdscj)
     else: 
         print ("putDesc(): no envelope in " + fdscj)
    except Exception as err: 
     print ("putDesc(): %s not found" % (fdscj))
 IN_ = utf8(IN_)
 
 # write the prepared descriptor to *info.txt
 
 shutil.copyfile(fname, fname+"._bak")
 F   = open(fname, "w")
 codecFail = False
 try: F.write(IN_)
 except Exception as err:
   codecFail = True
   print ("Failed putDesc(): " + str(err))
 F.close()

 if (codecFail): 
    shutil.copyfile(fname + "._bak", fname)
 os.remove(fname + "._bak")
 
 # set access time to created
 cr = IN["created"].split("-")
 if len(cr)>1:
    [y, m, d] = [int(cr[0]), int(cr[1]), int(cr[2])]
    t = datetime(y, m, d)
    t = time.mktime(t.timetuple())
    os.utime(fname, (t, t))

 # Check unusable entries
 unused = list(INkeys - set(["idrovi", "created", "urlrevrm"]))
 if (len(unused)>0):   print ("movinfo: Warning. Unusable entries %s" % (unused))
 if ("created" in IN): print ("movinfo: Created " + IN["created"])

 return
#----------------------------------------------------------------------------------------------------
# if newDesc=True,  create new Movie Descriptor using info from IMDB/omdb, Rovi
# if newDesc=False, update Movie Descriptor using its updated json Descriptor 
def procDesc(fname, newDesc, linkCheck, env):
 
 Res = getDesc(fname, newDesc)
 if (not "name" in Res or not "year" in Res): return
 name = Res["name"]
 year = Res["year"]
 if (newDesc):
    try: 
       fnamebak = fname.replace(".txt", ".bak")
       shutil.copy2(fname, fnamebak)
    except Exception as err:
       print ("movinfo: Failed to create " + fnamebak)
    if (not "created" in Res):
       now = time
       Res["created"] = now.strftime("%Y-%m-%d")
    Res = omdbget(Res)
    Res = roviget(Res)
     
 if (linkCheck): Res = checkLinks(Res)
 putDesc(fname, Res, env)

 return
#----------------------------------------------------------------------------------------------------
cfg = {} 
def getCfg():
  
  global cfg
 
  scriptdir = os.path.dirname(os.path.realpath(__file__))
  fn        = scriptdir.replace("\\", "/") + "/movinfo.json"
  if (not os.path.exists(fn)):
       print ("getCfg(): %s does not exist" % (fn))
       exit()
  try:
       cfg = json.loads(open(fn).read())
  except Exception as e:
       print ("getCfg(): wrong JSON in %s" % (fn))
       exit() 
  print ("getCfg(): using %s\n" % (fn))

  #print (cfg)
  issues = []
  if ("ROVI_SEARCH_KEY" not in cfg):    issues.append("ROVI_SEARCH_KEY")
  if ("ROVI_SEARCH_SECRET" not in cfg): issues.append("ROVI_SEARCH_SECRET")
  if ("OMDB_API_KEY" not in cfg):       issues.append("OMDB_API_KEY")
  
  if (len(issues)>0):
      print ("movinfo: missing %s" % (str(issues)))
      exit()
 
  return
#----------------------------------------------------------------------------------------------------
# desc can be info.txt or dscj.txt
# Find matching descriptor in the current dir or create a new one
def setDesc(desc):
 L = glob.glob("*" + desc)
 L.sort()
 res = ""
 if (len(L)>0): 
   res = L[0]
   return res # got desc
   
 # Create new desc using the current dir name
 cwd = os.getcwd().replace("\\", "/").split("/")[-1]
 p = re.compile("[^a-zA-Z0-9\.]")
 res = p.sub("", cwd) + "." + desc

 open(res, 'a').close()
 
 print ("setDesc: no descriptor found, created empty " + res)
 
 return res # new desc created
#----------------------------------------------------------------------------------------------------
def main():
  parser = argparse.ArgumentParser(description=help)
  group  = parser.add_mutually_exclusive_group(required=True)
  group.add_argument('-n', action="store_true", help="Create new descriptor(s) using DB info with 'name', 'year' as movie seach arguments")
  group.add_argument('-u', action="store_true", help="Update existing descriptor")
  group.add_argument('-ue', action="store_true", help="Update existing descriptor with envelope for JSON")
  parser.add_argument("-l", action="store_true", help="Check links for reviews")
  #parser.add_argument("path", type = str, help="Movie Descriptor(s) to process")

  args      = vars(parser.parse_args())
  env       = args["ue"]
  new       = args["n"]
  linkCheck = args["l"]
  
  getCfg()
  
  fname = setDesc("info.txt")
  print ("movinfo: using " + fname)
  
  dscj = fname.replace(".info.", ".dscj.")
  if (not os.path.exists(dscj)):
     open(dscj, 'a').close()
     print ("movinfo: created " + dscj)
  
  procDesc(fname, new, linkCheck, env)
  exit() 

#----------------------------------------------------------------------------------------------------
if __name__=="__main__": main()
exit()
