/* Day 5: -O0 vs -O2. Inlining, lea arithmetic, jump tables, loop layout.
 * At -O2, `square` and `classify` disappear into `run`. Find the switch's
 * jump table and count the remaining `call` instructions inside `run`. */
#include <stdio.h>
#include <stdlib.h>

static int classify(int v)
{
    switch (v & 7) {
    case 0: return 10;
    case 1: return 20;
    case 2: return 25;
    case 3: return 30;
    case 4: return 55;
    case 5: return 60;
    default: return -1;
    }
}

static int square(int v)
{
    return v * v;
}

__attribute__((noinline)) long run(const int *data, int n)
{
    long acc = 0;
    for (int i = 0; i < n; i++) {
        acc += square(data[i]) + classify(data[i]);
        if (acc > 1000000)
            acc -= 999999;
    }
    return acc;
}

int main(int argc, char **argv)
{
    int n = argc > 1 ? atoi(argv[1]) : 100;
    if (n < 1) n = 1;
    int *data = malloc((size_t)n * sizeof *data);
    if (!data) return 1;
    for (int i = 0; i < n; i++)
        data[i] = i * 7 + 3;
    long r = run(data, n);
    free(data);
    printf("%ld\n", r);
    return (int)(r & 0xff);
}
