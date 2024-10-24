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
# Version: 03/13/2021 - enabled extract() for -uxe
# Version: 03/21/2021 - use encoding='utf8' for open, close
# Version: 12/24/2021 - enable tmdb API by id instead of OMDB, ROVI
version = "07/21/2024"  # - now movinfo -n allows to specify urlimdb, urlwik in *.info.txt
version = "09/24/2024"  # - enabled -dimg to download images from IMDB
version = "10/22/2024"  # - minor fix of -n

import os, sys, datetime, re, json, copy
import platform
import shutil
import time
from datetime import datetime
import argparse, pprint
from builtins import str
import httplib2
import urllib.request
from iptcinfo3 import IPTCInfo

# For Python3, CentOS run:
# pip install httplib2

help = '''
Create/update movie descriptor *.info.txt using info from IMDB/TMDB.
Movie descriptor includes json and ASCII envelop, envelope is built from json.
After descriptor is created with -n option, json part can be updated manually. 
Then ASCII envelope is compiled from json by -ue option.
NOTE: Web service keys are kept in movinfo.json.
'''

# ----------------------------------------------------------------------------------------------------
# All symbols after x'80' => HTML encoding $#xxx;
def utf8(str):
    if (hasattr(str, "decode")):
        return str.decode('utf-8').encode('ascii', 'xmlcharrefreplace')
    else:
        return str.encode('ascii', 'xmlcharrefreplace').decode('utf-8')

# ----------------------------------------------------------------------------------------------------
# Set modified, access date time for fn. date is yyyy-mm-dd
def setModDate(fn, date):
    date = date.split("-")
    if len(date) == 3:
        [y, m, d] = [int(date[0]), int(date[1]), int(date[2])]
        t = datetime(y, m, d)
        t = time.mktime(t.timetuple())
        os.utime(fn, (t, t))

    return

# ----------------------------------------------------------------------------------------------------

def getDescHead():
    res = os.getcwd().replace("\\", "/").replace("_", "")
    res = res.split("/")[-1]
    return res

# ----------------------------------------------------------------------------------------------------------
# Check if y1 from the response matches with y2 in the descriptor
# y1 can be int or string
# y2 can be int or list of ints: 2000 or [2000, 2005, 2010]
# y1 matches OK if abs(y1-y2)=0
def checkYear(y1, y2):
    try:
        y1 = int(y1)
    except:
        return False

    if (y2.__class__.__name__ != "list"):
        y2 = [y2]

    for y in y2:
        if (abs(y1 - int(y)) <= 0): return True

    return False

# ----------------------------------------------------------------------------------------------------------
def getTmdbData(urlimdb, tmdbkey):
    if (not tmdbkey or type(tmdbkey) != str):
        print("getTmdbData(): wrong tmdbkey: " + str(tmdbkey))
        return False

    imdbId = ""
    if (urlimdb and "//www" in urlimdb and "/title/tt" in urlimdb):
        imdbId = urlimdb.split("title/")[1]
    if ("/" in imdbId): imdbId = imdbId.split("/")[0]
    if ("?" in imdbId): imdbId = imdbId.split("?")[0]

    if (not imdbId):
        print("getTmdbData(): can't get imdbId from [%s]" % (str(urlimdb)))
        return False

    id = imdbId
    reqMain = "https://api.themoviedb.org/3/movie/%s?api_key=%s" % (id, tmdbkey)
    reqCrew = "https://api.themoviedb.org/3/movie/%s/credits?api_key=%s" % (id, tmdbkey)

    print("getTmdbData(): stage 1 - try " + id)
    resp = None
    resMain = ""
    try:
        resp, resMain = httplib2.Http().request(reqMain)
    except:
        print("getTmdbData(): GET failed")
    status = ""
    if (resp and "status" in resp): status = str(resp.status)
    if (status != "200"):
        print("getTmdbData(): GET failed: " + status)
        return False

    resMain = str(utf8(resMain)).strip("b'")
    resMain = resMain.replace("\\'", "'")
    resMain = resMain.replace("\\\\\"", "'")

    try:
        res = json.loads(resMain)
    except Exception as err:
        print("getTmdbData(): Failed json load err=%s : %s" % (str(err), resMain))
        return False
    resMain = res
    res = ""

    print("getTmdbData(): stage 2")
    resCrew = ""
    try:
        resp, resCrew = httplib2.Http().request(reqCrew)
    except:
        print("getTmdbData(): GET failed")
    status = ""
    if ("status" in resp): status = str(resp.status)
    if (status != "200"):
        print("getTmdbData(): GET failed: " + status)
        return [resMain, False]

    resCrew = str(utf8(resCrew)).strip("b'")
    resCrew = resCrew.replace("\\'", "'")
    resCrew = resCrew.replace("\\\\\"", "'")
    res = ""
    try:
        res = json.loads(resCrew)
    except Exception as err:
        print("getTmdbData(): Failed json load - err=%s %s" % (str(err), resCrew))
        return [resMain, False]
    resCrew = False
    if ("cast" in res and "crew" in res): resCrew = res["cast"] + res["crew"]
    res = ""

    return [resMain, resCrew]

# ----------------------------------------------------------------------------------------------------------
def procTmdbData(IN):
    if (not IN):
        print("procTmdbData(): nothing to process")
        return False

    print("procTmdbData(): process main")
    main = IN[0]
    crew = IN[1]
    out = {}
    n = 0
    urlrev = [["", ""], ["", ""], ["", ""]]
    cast = [["", ""], ["", ""], ["", ""]]

    if ("title" in main):
        out["name"] = main["title"]
        n += 1
    if ("release_date" in main):
        year = main["release_date"].split("-")[0]
        out["year"] = int(year)
        n += 1
    if ("imdb_id" in main):
        out["urlimdb"] = "https://www.imdb.com/title/" + main["imdb_id"] + "/"
        n += 1
    if ("id" in main):
        curr = ["", "https://www.themoviedb.org/movie/" + str(main["id"])]
        urlrev.insert(0, curr)
        out["urlrev"] = urlrev
        n += 1
    if ("overview" in main):
        out["synopsis"] = main["overview"]
        n += 1

    out["director"] = ""
    out["cast"] = cast

    if (n != 5):
        print("procTmdbData(): Incomplete out: " + str(out))
        return False
    if (not crew): return out

    print("procTmdbData(): process crew")
    cast = []
    for item in crew:
        if ("job" in item and "name" in item):
            if (item["job"] != "Director" or not item["name"]): continue
            out["director"] = item["name"]
            continue
        if ("character" in item and "name" in item):
            if (not item["name"] or not item["character"]): continue
            curr = [item["name"], item["character"]]
            cast.append(curr)
    out["cast"] = cast
    now = datetime.now().strftime("%Y-%m-%d")
    out["created"] = IN[0].get("created", now)

    return out

# ----------------------------------------------------------------------------------------------------
# Remove items in IN["urlrev"] with unresolved links
def checkLinks(IN):
    if (not "urlrev" in IN): return IN
    rm = []
    OUT = []
    for el in IN["urlrev"]:
        try:
            resp, res = httplib2.Http().request(el[1])
        except:
            resp = {}
        if (not "status" in resp): resp["status"] = ""
        if (str(resp["status"]) != "200"):
            rm.append(str(el))
            print("movinfo: removed %s %s status=%s" % (el[0], el[1], resp["status"]))
        else:
            OUT.append(el)

    IN["urlrev"] = copy.deepcopy(OUT)

    if (len(rm) > 0):
        tmp = []
        if ("urlrevrm" in IN): tmp = IN["urlrevrm"]
        tmp = tmp + rm
        tmp = list(set(tmp))
        IN["urlrevrm"] = tmp
    return IN

# ----------------------------------------------------------------------------------------------------
# Check that certain entries are in IN and have proper format
def checkEntries(IN, new):
    if (new):
        allowed = {"created", "year", "name", "urlwik", "urlyou", "urlimdb", "urltmdb", "urlrev", "urlimg"}
        present = set(list(IN.keys()))
        extras = present - allowed
        if (len(extras) > 0):
            extras = list(extras)
            extras.sort()
            print("checkEntries(): entries not allowed for new and removed")
            pprint.pprint(extras)
            for el in extras: del IN[el]

    unfilled = []

    w = ""
    if ("urlwik" in IN and IN["urlwik"]):
        w = IN["urlwik"]
    if (not w.__class__.__name__ == "str"): w = ""
    if (w):
        IN["urlwik"] = copy.deepcopy([
            ["Film", w], ["", ""], ["", ""]
        ])
    if ("urlimg" not in IN):
        IN["urlimg"] = []
    if (IN["urlimg"].__class__.__name__ != "list"):
        print("checkEntries(): urlimg was not list, replaced by []")
        IN["urlimg"] = []
    OK = True
    # Check that these are lists of [string, string] pairs
    for el in ["urlwik", "urlyou", "urlrev", "cast"]:
        if (not el in IN or not IN[el]):
            IN[el] = copy.deepcopy([
                ["", ""], ["", ""], ["", ""]
            ])
            print("checkEntries(): added " + el)
            continue
        if (not IN[el].__class__.__name__ == "list"):
            print("movinfo.checkEntries(): Wrong %s" % (el))
            # pprint.pprint(In[el])
            OK = False
            continue
        for el_ in IN[el]:
            if (not el_.__class__.__name__ == "list"):
                print("movinfo.checkEntries(): Wrong %s" % (el))
                pprint.pprint(IN[el])
                OK = False
                continue
            if (len(el_) != 2):
                print("movinfo.checkEntries(): Wrong %s" % (el))
                pprint.pprint(IN[el])
                OK = False
                continue
            str = el_[0].__class__.__name__ == "str" or el_[0].__class__.__name__ == "unicode"
            str = str and (el_[1].__class__.__name__ == "str" or el_[1].__class__.__name__ == "unicode")
            if (len(el_) != 2 or not str):
                # print el_[0].__class__.__name__
                print("checkEntries(): Wrong %s" % (el))
                pprint.pprint(el_)
                OK = False
                continue

    unfilled.sort()
    if (len(unfilled) > 0 and not new): print("movinfo.checkEntries(): Warning. Missing/wrong entries %s" % (unfilled))

    return [OK, IN]

# ----------------------------------------------------------------------------------------------------
# remove commented entries ["#xxx", "yyy"]
def rmComments(IN):
    for el in list(IN.keys()):  # remove commented entries of the 1st level
        if (el != "" and el[0] == "#"): del IN[el]

    for el in ["cast", "urlwik", "urlrev"]:
        if el not in IN: continue
        out = []
        comm = False
        for item in IN[el]:
            if (item[0] != "" and item[0][0] == "#"): comm = True
            if (item[0] == "" or item[0][0] != "#"):  out.append(item)

        if (not comm): continue
        if (len(out) == 0):
            del IN[el]
            continue
        IN[el] = out

    return IN

# ----------------------------------------------------------------------------------------------------
# extract *.dscj.txt from *.info.txt if possible
def extract(fname):
    try:
        F = open(fname, "r", encoding='utf8')
        F_ = " " + utf8(F.read()) + " "
        F.close()
        if (not ("<!--info" in F_) or not ("<!--dscj" in F_)):
            print("extract(): Can't extract *dscj.txt from " + fname)
            return

        start = F_.find("<!--dscj") + len("<!--dscj")
        end = F_.find("-->", start)
        dscj = F_[start:end].strip()

        fnamej = fname.replace("info", "dscj")
        FW = open(fnamej, "w", encoding='utf8')
        FW.write(dscj)
        FW.close()
    except Exception as err:
        print("extract(): Failed %s err=%s" % (fname, err))
        return

    print("extract(): Created %s from %s" % (fnamej, fname))
    return

# ----------------------------------------------------------------------------------------------------
# Descriptor in the file fname => IN dictionary
def getDesc(fname, isNew):
    try:
        F = open(fname, "r", encoding='utf8')
        F_ = " " + utf8(F.read()) + " "
        # get json descriptor
        if ("<!--info" in F_):
            F_ = F_.split("<!--info")
            if ("-->" in F_[1]):
                F_ = F_[1].split("-->")
            else:
                F_ = F_[1].split("->")
        else:
            F_ = [F_]
        IN = json.loads(F_[0])
        F.close()
        # print (IN)
        # exit
    except:
        print("getDesc(): wrong json in %s" % fname)
        return {}
    if (not "urlimdb" in IN):
        print("getDesc(): no urlimdb in %s" % fname)
        return {}

    [OK, IN] = checkEntries(IN, isNew)
    if (not OK): return []
    if (not isNew): IN = rmComments(IN)

    return IN

# ----------------------------------------------------------------------------------------------------
# <a *>X</a> => X
def procAtag(IN):
    if (IN.find("<a ") < 0): return IN

    p = re.compile("<a [^>]+>")
    IN = p.sub("", IN)
    IN = IN.replace("</a>", "")

    return IN

# ----------------------------------------------------------------------------------------------------
def putDesc(fname, IN, env):
    INkeys = set(list(IN.keys()))
    INkeys = INkeys - {"name", "year"}

    HeaderYear = ""
    if ("year" in IN): HeaderYear = IN["year"]
    if (HeaderYear.__class__.__name__ == "list"): HeaderYear = HeaderYear[0]
    Header = "%s (%s)" % (IN["name"], HeaderYear)

    dir = ""  # director
    if ("director" in IN): dir = "<b>Director:</b> %s\n" % (IN["director"])
    INkeys = INkeys - {"director"}

    syn = ""  # synopsis
    if ("synopsis" in IN): syn = "<b>Synopsis:</b> %s\n" % (IN["synopsis"])
    syn = procAtag(syn)
    INkeys = INkeys - {"synopsis"}

    imdb = ""  # IMDB link
    if ("urlimdb" in IN): imdb = IN["urlimdb"]
    INkeys = INkeys - {"urlimdb"}

    cast = ""
    if ("cast" in IN and len(IN["cast"]) > 0):
        for el in IN["cast"]:
            cast = cast + el[0]
            if (el[1] != ""):
                cast = cast + " as <b>" + el[1] + "</b>, "
            else:
                cast = cast + ", "
        cast = "<b>Cast:</b> %s\n" % (cast[0:len(cast) - 2])
        cast = cast.replace(", \n", "\n")
        # print("===>" + cast + str(cast.endswith(", \n")))
    INkeys = INkeys - {"cast"}

    rev = ""  # reviews links
    if ("urlrev" in IN and len(IN["urlrev"]) > 0):
        for el in IN["urlrev"]:
            # print (el)
            if (len(el[0]) > 0):
                rev = "%s%s: %s\n" % (rev, el[0], el[1])
            else:
                rev = "%s%s\n" % (rev, el[1])
    rev = rev.strip()
    if (rev != ""): rev = rev + "\n"

    INkeys = INkeys - {"urlrev"}

    wik = ""  # wiki links
    if ("urlwik" in IN and len(IN["urlwik"]) > 0):
        if (IN["urlwik"].__class__.__name__ == "str"): IN["urlwik"] = [["Wiki", IN["urlwik"]]]
        for el in IN["urlwik"]:
            if (len(el[0]) > 0):
                wik = "%s%s: %s\n" % (wik, el[0], el[1])
            elif (len(el[1]) > 0):
                wik = "%sWiki: %s\n" % (wik, el[1])
    #       else:              wik = "%s%s\n % (wik, el[1])

    INkeys = INkeys - {"urlwik"}

    you = ""  # youtube links
    if ("urlyou" in IN and len(IN["urlyou"]) > 0):
        if (IN["urlyou"].__class__.__name__ == "str"): IN["urlyou"] = [["Youtube", IN["urlyou"]]]
        for el in IN["urlyou"]:
            if (len(el[0]) > 0 and not el[0].startswith("Youtube")): el[0] = "Youtube. " + el[0]
            if (len(el[0]) > 0):
                you = "%s%s: %s\n" % (you, el[0], el[1])
            else:
                you = "%s%s\n" % (you, el[1])
    you = you.strip()
    if (you != ""): you = you + "\n"

    INkeys = INkeys - {"urlyou"}

    if ("created" not in IN): IN["created"] = ""

    print("putDesc(): env=" + str(env))
    if (env):
        _imdb = imdb.replace("http://", "")
        _imdb = _imdb.replace("https://", "")
        IN_ = "<!-%s %s %s->\n" % (IN["created"], Header, _imdb)
        IN_ = IN_ + dir + syn + cast + "<b>Links</b>\n" + wik + rev + you
        IN_ = IN_ + "<!--info\n%s-->\n" % (json.dumps(IN, indent=1))
    else:
        IN_ = json.dumps(IN, sort_keys=True, indent=1)

    # append *dscj.txt if there is one
    fdscj = fname.replace("info.txt", "dscj.txt")
    if (env and os.path.exists(fdscj)):
        try:
            F = open(fdscj, "r", encoding='utf8')
            F_ = F.read()
            if ("<!--dscj" in F_):
                IN_ = IN_ + F_
                print("putDesc(): Appended " + fdscj)
            else:
                print("putDesc(): No envelope in " + fdscj)
        except Exception as err:
            print("putDesc(): %s not found" % (fdscj))
    IN_ = utf8(IN_)

    # write the prepared descriptor to *info.txt

    shutil.copyfile(fname, fname + "._bak")
    F = open(fname, "w", encoding='utf8')
    codecFail = False
    try:
        F.write(IN_)
    except Exception as err:
        codecFail = True
        print("Failed putDesc(): " + str(err))
    F.close()

    if (codecFail):
        shutil.copyfile(fname + "._bak", fname)
    os.remove(fname + "._bak")

    setModDate(fname, IN["created"])

    # Check unusable entries
    unused = list(INkeys - {"created", "urlrevrm", "urlimg"})
    if (len(unused) > 0): print("putDesc(): Warning. Unusable entries %s" % (unused))
    if ("created" in IN): print("putDesc(): Created %s (%s)" % (fname, IN["created"]))

    return

# ----------------------------------------------------------------------------------------------------
# if newDesc=True,  create new Movie Descriptor using info from IMDB/tmdb
# if newDesc=False, update Movie Descriptor using its updated json Descriptor
def procDesc(fname, newDesc, linkCheck, env):
    Res = getDesc(fname, newDesc)
    if (not "urlimdb" in Res):
        print("procDesc(): no urlimdb in " + fname)
        return
    urlimdb = Res.get("urlimdb", "")
    urlwik = Res.get("urlwik", "")
    urlyou = Res.get("urlyou", "")
    urlimg = Res.get("urlimg", [])

    fnamebak = ""
    if (newDesc):
        try:
            fnamebak = fname.replace(".txt", ".bak")
            shutil.copy2(fname, fnamebak)
        except Exception as err:
            print("procDesc(): Failed to create " + fnamebak)
        Res = getTmdbData(urlimdb, cfg["TMDB_API_KEY"])
        Res = procTmdbData(Res)

    if (not Res): return
    if (not "name" in Res):
        print("procDesc(): can't get name, try movinfo -n")
        pprint.pprint(Res)
        return
    Res["urlimdb"] = urlimdb
    Res["urlwik"] = urlwik
    Res["urlyou"] = urlyou
    Res["urlimg"] = urlimg
    if (linkCheck): Res = checkLinks(Res)
    putDesc(fname, Res, env)

    return

# ----------------------------------------------------------------------------------------------------
cfg = {}
def getCfg():
    global cfg

    scriptdir = os.path.dirname(os.path.realpath(__file__))
    fn = scriptdir.replace("\\", "/") + "/movinfo.json"
    if (not os.path.exists(fn)):
        print("getCfg(): %s does not exist" % (fn))
        exit()
    try:
        cfg = json.loads(open(fn).read())
    except Exception as e:
        print("getCfg(): wrong JSON in %s" % (fn))
        exit()
    print("getCfg(): using " + fn)

    # print (cfg)
    issues = []
    if ("TMDB_API_KEY" not in cfg):
        issues.append("TMDB_API_KEY")

    if (len(issues) > 0):
        print("getCfg(): Missing %s" % (str(issues)))
        exit()

    return

# ----------------------------------------------------------------------------------------------------
# Find matching descriptor in the current dir or create a new one
def setDesc(desc):
    fn = getDescHead() + "." + desc
    if (os.path.exists(fn)):
        return fn  # got desc

    # Create new desc
    jdesc = '{"urlimdb": "", "urlwik": ""}'
    F = open(fn, "w", encoding='utf8')
    try:
        F.write(jdesc)
    except Exception as err:
        print("Failed setDesc(): " + str(err))
    F.close()
    print("setDesc(): created empty " + fn)

    exit()

# ----------------------------------------------------------------------------------------------------
def iptcSet(fn, capt, spins):
    if (not capt and not spins): return

    if (capt == ""):  capt = " "
    if (spins == ""): spins = " "
    now = datetime.now()
    now = now.strftime("%Y%m%d%H%M%S")
    info = None
    sys.stdout = open(os.devnull, 'w')  # disable print to block warning msgs
    n = 0
    try:
        n = 1
        info = IPTCInfo(fn, force=True)
        n = 2
        if (hasattr(info, "data")):  # python 2
            if (capt):  info.data['caption/abstract'] = capt
            if (spins): info.data['special instructions'] = spins
            info.data['date created'] = now
            info.data['writer/editor'] = "picman"
            # info.data['copyright notice'] = ""
            # info.data['keywords']  = ""
        else:  # python 3
            if (capt):  info['caption/abstract'] = capt
            if (spins): info['special instructions'] = spins
            info['date created'] = now
            info['writer/editor'] = "picman"
            # info['copyright notice'] = ""
            # info['keywords']  = ""
        n = 3
        time.sleep(0.25)
        info.save()
        if (os.path.isfile(fn + "~")): os.remove(fn + "~")
        sys.stdout = sys.__stdout__  # enable print
    except Exception as e:
        info = None
        sys.stdout = sys.__stdout__  # enable print
        # print ("[%s]" % (capt))
        print("iptcSet() failed to process %s - %d %s" % (fn, n, str(e)))
    return

# ----------------------------------------------------------------------------------------------------
def getImdbImage(url):
    if (not url or not url.startswith("https://www.imdb.com/title/")):
        print("getImdbImage(): skip this url: " + str(url))
        return False
    if ("/mediaviewer/rm" not in url):
        print("getImdbImage(): no image id in url")
        return False
    if ("/?"):
        url = url.split("/?")[0]
    imgId = url.split("/mediaviewer/")[1]
    if ("/" in imgId):
        imgId = imgId.split("/")[0]
    fn = "imdbimg." + imgId + ".jpg"
    if (os.path.isfile(fn)):
        print("getImdbImage(): %s already exists - skip" % fn)
        return True

    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml; image/avif,image/webp')
    req.add_header('Accept-Language', 'en-US')
    res = ""
    try:
        res = urllib.request.urlopen(req).read().decode('utf-8')
    except Exception as e:
        print("getImdbImage(): request failed for %s err=%s" % (url, str(e)))
        return False

    resTitle = res.split("<meta property=\"og:title\" content=")
    if (len(resTitle)<2):
        print("getImdbImage(): can't get title")
        return False

    resTitle = resTitle[1].split("\"")
    if (len(resTitle) <3 ):
        print("getImdbImage(): can't get title")
        return False
    title = resTitle[1]
    if (not title):
        print("getImdbImage(): wrong title")
        return False

    resDesc = res.split("<meta property=\"og:description\" content=")
    if (len(resDesc)<2):
        print("getImdbImage(): can't get description")
        return False
    resDesc = resDesc[1].split(".jpg")
    if (len(resDesc) < 2):
        print("getImdbImage(): can't get description")
        return False
    resDesc = resDesc[0] + ".jpg"
    resDesc = resDesc.split("\"")
    if (len(resDesc) < 3):
        print("getImdbImage(): can't get caption, imgUrl")
        return False
    caption = resDesc[1].replace(" in " + title, "").replace(" and ", ", ").replace(",,", ",")
    imgUrl = resDesc[-1]
    if (not imgUrl.startswith("https://")):
        print("getImdbImage(): can't get caption, imgUrl")
        return False
    print("getImdbImage(): processing " + str([title, caption]))

    req = urllib.request.Request(imgUrl)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml; image/avif,image/webp')
    req.add_header('Accept-Language', 'en-US')
    try:
        res = urllib.request.urlopen(req).read()
        with open(fn, 'wb') as f:
            f.write(res)
            f.close()
    except Exception as e:
        print("getImdbImage(): can't download image %s=>%s - %s" %(imgUrl, fn, str(e)))
        return False
    iptcSet(fn, caption, None)
    print("getImdbImage(): processed " + fn)

    return True

# ----------------------------------------------------------------------------------------------------
# get images from IMDB, they are specified in *.info.txt, tag urlimg
def procDimg():
    fn   = getDescHead() + ".info.txt"
    desc = getDesc(fn, False)
    print("procDimg(): using " + fn)
    urlimg = []
    if ("urlimg" in desc):
        urlImg = desc["urlimg"]
    if (not urlImg):
        print("procDimg(): nothing to process")
        return
    for url in urlImg:
        getImdbImage(url)

    print("procDimg(): processed %d items" % len(urlImg))
    return

# ----------------------------------------------------------------------------------------------------
def main():
    pyVer = platform.python_version()
    print("movinfo: start version: %s with Python: %s at: %s" % (version, pyVer, os.getcwd().replace("\\", "/")))

    parser = argparse.ArgumentParser(description=help)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-n', action="store_true",
                       help="Create new descriptor(s) using DB info with 'name', 'year' as movie search arguments")
    group.add_argument('-u', action="store_true", help="Update existing descriptor")
    group.add_argument('-ue', action="store_true", help="Update existing descriptor with envelope for JSON")
    group.add_argument('-uxe', action="store_true", help="extract *.dscj.txt from envelope")
    group.add_argument('-dimg', action="store_true", help="download images from imdb using urlimg tag")
    parser.add_argument("-l", action="store_true", help="Check links for reviews")

    args = vars(parser.parse_args())
    env = args["ue"]
    xenv = args["uxe"]
    new = args["n"]
    dimg = args["dimg"]
    linkCheck = args["l"]

    getCfg()

    fname = setDesc("info.txt")
    print("movinfo: using " + fname)

    dscj = fname.replace(".info.", ".dscj.")
    if (not os.path.exists(dscj)):
        F = open(dscj, 'w')
        F.write("{}\n")
        F.close()
        print("movinfo: created empty " + dscj)

    if (xenv):
        extract(fname)
        exit()

    if (dimg):
        procDimg()
        exit()

    procDesc(fname, new, linkCheck, env)
    exit()

# ----------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
exit()
