#include "inode.h"

struct inode *inode_find(struct inode *node, char *name) {
    unsigned int bucket = hash_name(name);
    struct entry *entry = node->dir->tb[bucket];
    
    while (entry != NULL) {
        if (entry->name != NULL && name != NULL) {
            if (strcmp(entry->name, name) == 0) {
                return (struct inode *)entry->inum;
            }
        }
        entry = entry->next;
    }
    
    return NULL;
}