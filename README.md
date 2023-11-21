# Usage


## Recording Data

Without arguments, ftrace-callgrapher will by default capture trace data on all
CPUs for 10 seconds:

```
$ sudo ftrace-callgrapher.py record
```

This will generate huge amount of data, even for the later post processing. If
data can be filtered in the recoring phase 

```
$ sudo ftrace-callgrapher.py record --cpu 1 --record-time 30
```

## Visualizing Recorded Data

```
$ ftrace-callgrapher.py visualize --filter-filepath net
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

