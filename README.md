OS:             Win10

Python Version: 3.11.5

usage: movinfo.py [-h] (-n | -u | -ue | -uxe) [-l]
Create/update movie descriptor *.info.txt using info from IMDB/TMDB. Movie descriptor includes json and ASCII envelope,
envelope is built from json. After descriptor is created with -n option, json part can be updated manually. Then ASCII
envelope is compiled from json by -ue option. 
NOTE: Web service keys are kept in movinfo.json.
<pre>
options:
  -h, --help  show this help message and exit
  -n          Create new descriptor(s) using DB info with 'name', 'year' as movie seach arguments
  -u          Update existing descriptor
  -ue         Update existing descriptor with envelope for JSON
  -uxe        extract *dscj from envelope
  -l          Check links for reviews
</pre>
