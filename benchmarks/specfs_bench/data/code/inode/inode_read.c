#include "inode.h"

struct read_ret* inode_read(struct inode* node, unsigned len, unsigned offset) {
    struct read_ret* ret = malloc_readret();
    
    // Case 1: Empty read range
    if (offset >= node->size || len == 0) {
        ret->num = 0;
        ret->buf = NULL;
        return ret;
    }
    
    // Case 2: Data is read
    unsigned actual_len = (len < node->size - offset) ? len : node->size - offset;
    ret->num = actual_len;
    ret->buf = malloc_buffer(actual_len);
    
    file_read(node, offset, actual_len, ret->buf);
    
    return ret;
}