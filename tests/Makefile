CC = gcc
CFLAGS = -Wall -pthread

.SUFFIXES: .c .out

SRC = $(wildcard *.c)
TARGETS = $(patsubst %.c, %, $(SRC))

all: $(TARGETS)

.c.out:
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TARGETS)

bench:
	taskset -c 1 ./echo-service.out
