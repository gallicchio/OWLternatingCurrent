/* jsonbuf.h: appending to a fixed buffer that never overflows (the console's replies). */
#pragma once
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>

typedef struct {
    char *buf;
    size_t n, k;
} jsonbuf;

static inline jsonbuf jb_start(char *buf, size_t n)
{
    jsonbuf j = {buf, n, 0};
    if (n)
        buf[0] = 0;
    return j;
}

__attribute__((format(printf, 2, 3))) static inline void jb_add(jsonbuf *j, const char *fmt, ...)
{
    if (j->k + 1 >= j->n)
        return;
    va_list ap;
    va_start(ap, fmt);
    int w = vsnprintf(j->buf + j->k, j->n - j->k, fmt, ap);
    va_end(ap);
    if (w < 0)
        return;
    j->k += (size_t)w;
    if (j->k >= j->n)
        j->k = j->n - 1;
}
