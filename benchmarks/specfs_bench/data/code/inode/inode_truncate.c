#include "inode.h"

void inode_truncate(struct inode* node, unsigned size) {
    if (size < node->size) {
        // Case 1: Truncate - clear the bytes beyond the new size
        file_clear(node, size, node->size - size);
        node->size = size;
    } else if (size > node->size) {
        // Case 2: Extend - allocate and clear additional space
        file_allocate(node, node->size, size - node->size);
        file_clear(node, node->size, size - node->size);
        node->size = size;
    }
    // If size == node->size, do nothing
}