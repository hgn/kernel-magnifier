<p align="center">
  <img src="docs/kernel-magnifier-readme.png" alt="Kernel Magnifier"><br>
</p>

*A Linux Kernel Execution Flow Research Tool for Upcomming Kernel Hackers and Veterans*

## Background

You are new to Linux kernel development and want to develop a driver,
contribute new network stack functionality, better understand the complex
process scheduler or just chase a kernel bug - then the Kernel Magnifier could
provide some support.

Many developers find it difficult to understand the kernel. It is not simple
code, on the contrary: even if you have mastered programming languages such as
C/C++, it is incredibly tedious to understand the kernel. This is due to the
following reasons, among others

- The Linux kernel has its very own runtime, which is completely different from
  userspace. There are many execution contexts which are complex even for
  experienced kernel developers
- Many things are processed asynchronously! Top and bottom halves from the
  Informatics lecture are still familiar to many. But the kernel is much more
  complex here. There are softwirqs, workers, tasklets and other context and
  subsystem add custom implementations - like for NAPI for the network stack -
  on top of it. None of this makes the kernel any simpler.
- The kernel is highly optimized, often every instruction is optimized to
  elicit the last percent of performance
- Many indirect functions via function pointers are included in the kernel,
  e.g. fileops structure.
- The kernel has grown over decades - technical debts have also accumulated
  here, which do not make the whole thing any easier


## Usage


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

