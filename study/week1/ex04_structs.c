/* Day 4: structs, pointer chains, and a TABLE OF FUNCTION POINTERS.
 * This is the same shape as a driver filling IDD_CX_CLIENT_CONFIG with
 * callbacks and a framework later calling them.
 * Exercise: open the STRIPPED Windows -O2 build (make stripped) and recover
 * Device, Monitor and Callbacks in Ghidra's Data Type Manager without
 * looking at this file. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Monitor {
    unsigned id;
    unsigned width;
    unsigned height;
    unsigned refresh;
    struct Monitor *next;
} Monitor;

typedef struct Callbacks {
    int  (*on_arrive)(Monitor *m);
    int  (*on_frame)(Monitor *m, const void *buf, size_t n);
    void (*on_depart)(Monitor *m);
} Callbacks;

typedef struct Device {
    char name[32];
    unsigned flags;
    Monitor *monitors;
    Callbacks cb;
    unsigned long long frames_seen;
} Device;

static unsigned next_id = 100;

static int arrive(Monitor *m)
{
    printf("arrive %u %ux%u@%u\n", m->id, m->width, m->height, m->refresh);
    return 0;
}

static int frame(Monitor *m, const void *buf, size_t n)
{
    (void)buf;
    return (int)(n ^ m->id);
}

static void depart(Monitor *m)
{
    printf("depart %u\n", m->id);
}

__attribute__((noinline)) void device_init(Device *d, const char *name)
{
    memset(d, 0, sizeof *d);
    strncpy(d->name, name, sizeof d->name - 1);
    d->flags = 0x10;
    d->cb.on_arrive = arrive;      /* <- three consecutive code-address stores */
    d->cb.on_frame  = frame;
    d->cb.on_depart = depart;
}

__attribute__((noinline)) Monitor *device_add_monitor(Device *d, unsigned w, unsigned h)
{
    Monitor *m = calloc(1, sizeof *m);
    if (!m)
        return NULL;
    m->id = next_id++;
    m->width = w;
    m->height = h;
    m->refresh = 60;
    m->next = d->monitors;
    d->monitors = m;
    d->cb.on_arrive(m);
    return m;
}

__attribute__((noinline)) int device_pump(Device *d, const void *buf, size_t n)
{
    int r = 0;
    for (Monitor *m = d->monitors; m; m = m->next) {
        r += d->cb.on_frame(m, buf, n);
        d->frames_seen++;
    }
    return r;
}

int main(void)
{
    Device dev;
    char buf[16] = {0};
    device_init(&dev, "lci");
    device_add_monitor(&dev, 1920, 1080);
    device_add_monitor(&dev, 2048, 1536);
    int r = device_pump(&dev, buf, sizeof buf);
    for (Monitor *m = dev.monitors; m;) {
        Monitor *n = m->next;
        dev.cb.on_depart(m);
        free(m);
        m = n;
    }
    printf("frames_seen=%llu\n", dev.frames_seen);
    return r & 0xff;
}
