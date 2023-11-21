# Usage


## Recording Data

Without arguments, ftrace-callgrapher will by default capture trace data on all
CPUs for 10 seconds:

```
$ sudo ftrace-callgrapher.py record
```

This will generate huge amount of data, even for the later post processing. If
data can be filtered in the recoring phase: perfect. Two options allow
filtering for now: the recorded time and a filter on what CPUs recording should
be done. The later is really important especially on 16+ multi-core systems.

```
$ ftrace-callgrapher.py record --record-time 10 --cpumask 1
Record mode - now starting recording traces for 10.0 seconds
Limit recording to CPU mask 1
Wrote data to ftrace-callgrapher.data
Recorded filesize: 199.38 MiB
```

## Visualizing Recorded Data

Visualization is quite ease, kust call with visualize as an argument:

```
$ ftrace-callgrapher.py visualize
Visualization mode - now generating visualization...
parsing completed, found 2316184 events
function-calls.png generated
ftrace-callgrapher.pdf generated
```

For symbol path filtering a mapping table `function name` to `filename` must be generated:

```
ftrace-callgrapher.py generate-symbol-map -k /usr/lib/debug/boot/vmlinux-$(uname -r)
```

```
$ ftrace-callgrapher.py visualize --filter-filepath net
Visualization mode - now generating visualization...
parsing completed, found 2316184 events
function-calls.png generated
ftrace-callgrapher.pdf generated
```


# Installation

ftrace-callgrapher requires optionally debug symbols to map symbols to source
code files. For the actual mapping we use the dwarf information, to get the
data the tool use dwarfdump, so just install the packages

> NOTE: this will consume 600MiB of harddisk

```
# Mandatory
$ apt-get install python3-pygraphviz
# Optional, for symbol filtering required
$ apt-get install dwarfdump 
$ apt-get install linux-image-amd64-dbg
```

