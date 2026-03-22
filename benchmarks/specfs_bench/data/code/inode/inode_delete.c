#include "inode.h"

struct inode* inode_delete(struct inode* inum, char* name) {
    if (inum == NULL || inum->dir == NULL || name == NULL) {
        return NULL;
    }
    
    unsigned int bucket_idx = hash_name(name);
    struct entry** prev_ptr = &(inum->dir->tb[bucket_idx]);
    struct entry* current = *prev_ptr;
    
    while (current != NULL) {
        if (current->name != NULL && strcmp(current->name, name) == 0) {
            // Found the entry to delete
            *prev_ptr = current->next;
            
            // Get the inode pointer to return
            struct inode* result = (struct inode*)current->inum;
            
            // Free the entry
            free_entry(current);
            
            // Decrease directory size
            inum->size--;
            
            return result;
        }
        prev_ptr = &(current->next);
        current = current->next;
    }
    
    // Entry not found
    return NULL;
}