OS:             Win10
<pre>
movinfo: start version: 09/24/2024 with Python: 3.11.5 at: j:/jblog/run
usage: movinfo.py [-h] (-n | -u | -ue | -uxe | -dimg) [-l]

Create/update movie descriptor *.info.txt using info from IMDB/TMDB. Movie
descriptor includes json and ASCII envelop, envelope is built from json. After
descriptor is created with -n option, json part can be updated manually. Then
ASCII envelope is compiled from json by -ue option. NOTE: Web service keys are
kept in movinfo.json.

options:
  -h, --help  show this help message and exit
  -n          Create new descriptor(s) using DB info with 'name', 'year' as
              movie search arguments
  -u          Update existing descriptor
  -ue         Update existing descriptor with envelope for JSON
  -uxe        extract *.dscj.txt from envelope
  -dimg       download images from imdb using urlimg tag
  -l          Check links for reviews
</pre>
