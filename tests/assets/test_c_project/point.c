#include "point.h"

// Point method implementations
void point_move(Point* p, int dx, int dy) {
    p->x += dx;
    p->y += dy;
}

void point_print(const Point* p) {
    // printf("Point(%d, %d)\n", p->x, p->y);
}

int point_distance_squared(const Point* a, const Point* b) {
    int dx = a->x - b->x;
    int dy = a->y - b->y;
    return dx * dx + dy * dy;
}

Point point_create(int x, int y) {
    Point p = {x, y};
    return p;
}

// Utility functions
int max(int a, int b) {
    return (a > b) ? a : b;
}

void init_system() {
    // System initialization
}
