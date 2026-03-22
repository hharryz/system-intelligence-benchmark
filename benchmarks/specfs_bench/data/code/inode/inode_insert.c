#include "inode.h"

int inode_insert(struct inode* cur, struct inode* inum, char* name) {
    unsigned int hash = hash_name(name);
    struct entry *new_entry = malloc_entry();
    if (new_entry == NULL) {
        return 1;
    }
    
    char *name_copy = malloc_string(name);
    if (name_copy == NULL) {
        free(new_entry);
        return 1;
    }
    
    new_entry->name = name_copy;
    new_entry->inum = inum;
    
    // Insert at head of the bucket
    new_entry->next = cur->dir->tb[hash];
    cur->dir->tb[hash] = new_entry;
    
    // Increase size of cur inode
    cur->size += 1;
    
    return 0;
}