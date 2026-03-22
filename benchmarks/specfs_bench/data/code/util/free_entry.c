#include "util.h"

void free_entry(struct entry* en) {
    if (en != NULL) {
        if (en->name != NULL) {
            free(en->name);
        }
        free(en);
    }
}