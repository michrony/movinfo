OS:             Win7

Python Version: 2.7

usage: movinfo.py [-h] (-n | -u | -ue) [-l] path

Create/update movie descriptor *.info.txt using info from Rotten Tomatoes,
IMDB/omdb, Rovi. Movie descriptor includes json and ASCII envelop, envelope is
built from json. After descriptor is created with -n option, json part can be
updated manually. Then ASCII envelope is compiled from json by -ue option.
NOTE: Web service keys are kept in movinfo.json.

positional arguments:
  path        Movie Descriptor(s) to process

optional arguments:
  -h, --help  show this help message and exit
  -n          Create new descriptor(s) using DB info with 'name', 'year' as
              movie seach arguments
  -u          Update existing descriptor
  -ue         Update existing descriptor with envelope for JSON
  -l          Check links for reviews
