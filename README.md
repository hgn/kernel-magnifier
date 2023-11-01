# Usage

```
$ ftrace-callgrapher.py visualize --filter-filepath net,kernel
```


# Installation

ftrace-callgrapher need debug symbols to map symbols to source code files.
For the actual mapping we use the dwarf information, to get the data the tool
use dwarfdump, so just install the packages

> NOTE: this will consume 600MiB of harddisk

```
# Mandatory
$ apt-get install python3-pygraphviz
# Optional, for symbol filtering required
$ apt-get install dwarfdump 
$ apt-get install linux-image-amd64-dbg
```

