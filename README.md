usage: movinfo.py [-h] (-n | -u) [-l] path

Create/update movie descriptor *.info.txt using info from Rotten Tomatoes,
Netflix, IMDB/omdb, Rovi. Movie descriptor includes json and plain ASCII
parts, ASCII is built from json. After descriptor is created with -n option,
json part can be updates manually. Then ASCII part is compiled from json by -u
option.

positional arguments:
  path        Movie Descriptor(s) to process

optional arguments:
  -h, --help  show this help message and exit
  
  -n          Create new descriptor(s) using DB info with 'name', 'year' as
              movie seach arguments
  
  -u          Update existing
  
  -l          Check links for reviews
