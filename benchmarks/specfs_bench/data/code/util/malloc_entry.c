#include "util.h"

struct entry *malloc_entry() {
    return (struct entry *)malloc(sizeof(struct entry));
}