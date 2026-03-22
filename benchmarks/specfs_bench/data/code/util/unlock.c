#include "util.h"

void unlock(struct inode* inum) {
    mcs_node_t *node = inum->hd;
    inum->mutex = 0;
    mcs_mutex_unlock(inum->impl, node);
    free(node);
}