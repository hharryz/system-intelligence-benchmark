#include "util.h"

void lock(struct inode* inum) {
    mcs_node_t *node = (mcs_node_t *)malloc(sizeof(mcs_node_t));
    mcs_mutex_lock(inum->impl, node);
    inum->hd = node;
    inum->mutex = (int)syscall(SYS_gettid);
}