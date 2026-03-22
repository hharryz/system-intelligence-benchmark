#include "file.h"

void file_allocate(struct inode *node, unsigned offset, unsigned len) {
    unsigned start_page = offset / PG_SIZE;
    unsigned end_page = (offset + len - 1) / PG_SIZE;
    
    for (unsigned i = start_page; i <= end_page; i++) {
        if (node->file->index[i] == NULL) {
            node->file->index[i] = malloc_page();
        }
    }
}