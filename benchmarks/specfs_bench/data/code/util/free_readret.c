#include "util.h"

void free_readret(struct read_ret *p) {
    if (p != NULL) {
        if (p->buf != NULL) {
            free(p->buf);
        }
        free(p);
    }
}