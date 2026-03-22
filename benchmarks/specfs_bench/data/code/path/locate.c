#include "path.h"

struct inode* locate(struct inode* cur, char* path[]) {
    struct inode* current = cur;
    int i = 0;

    // Handle empty path case: return original locked cur
    if (path[0] == NULL) {
        return current;
    }

    // Traverse each path component
    while (path[i] != NULL) {
        struct inode* next = inode_find(current, path[i]);
        
        // If component not found, unlock current and return NULL
        if (next == NULL) {
            unlock(current);
            return NULL;
        }
        
        // Lock coupling: lock next before unlocking current
        lock(next);
        unlock(current);
        current = next;
        i++;
    }

    return current;
}