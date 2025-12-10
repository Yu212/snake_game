North = 0
East = 1
South = 2
West = 3

FREE = 0
FORBIDDEN = 1
MUST = 2

N = 32
tail_pos = (0, 0)
head_pos = (0, 0)
body = []
length = 1
tree = None
hamilton_cycle = None
apple_pos = None

def moved_pos(pos, dir):
    x, y = pos
    if dir == North: return (x, y + 1)
    if dir == East: return (x + 1, y)
    if dir == South: return (x, y - 1)
    if dir == West: return (x - 1, y)
    raise ValueError("Invalid direction")

def in_bounds(pos, n):
    x, y = pos
    return 0 <= x < n and 0 <= y < n

def do_move(direction):
    global tail_pos, head_pos, body, length
    head_pos = moved_pos(head_pos, direction)
    body.append(direction)
    if length <= len(body):
        first_dir = body.pop(0)
        tail_pos = moved_pos(tail_pos, first_dir)
    if head_pos == apple_pos:
        length += 1
    move(direction)

def set_tree_restriction(tree_pos, dir, restriction):
    global tree
    opposite = moved_pos(tree_pos, dir)
    assert {tree[tree_pos][dir], restriction} != {MUST, FORBIDDEN}
    assert {tree[opposite][(dir+2)%4], restriction} != {MUST, FORBIDDEN}
    tree[tree_pos][dir] = restriction
    tree[opposite][(dir+2)%4] = restriction

def calc_walk_restrictions(pos, dir):
    nxt = moved_pos(pos, dir)
    tree_cur = (pos[0] // 2, pos[1] // 2)
    tree_nxt = (nxt[0] // 2, nxt[1] // 2)
    if tree_cur == tree_nxt:
        if in_bounds(moved_pos(tree_cur, (dir+3)%4), N//2):
            set_tree_restriction(tree_cur, (dir+3)%4, FORBIDDEN)
    else:
        set_tree_restriction(tree_cur, dir, MUST)

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, u):
        if self.parent[u] == u:
            return u
        self.parent[u] = self.find(self.parent[u])
        return self.parent[u]
    
    def same(self, u, v):
        return self.find(u) == self.find(v)

    def union(self, u, v):
        root_u = self.find(u)
        root_v = self.find(v)
        if root_u != root_v:
            if self.size[root_u] < self.size[root_v]:
                root_u, root_v = root_v, root_u
            self.parent[root_v] = root_u
            self.size[root_u] += self.size[root_v]

    def copy(self):
        new_uf = UnionFind(0)
        new_uf.parent = self.parent[:]
        new_uf.size = self.size[:]
        return new_uf

def distance(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def calc_shortest_path():
    global tree
    cur_pos = tail_pos
    restrict = False
    for i, body_dir in enumerate(body):
        if distance(head_pos, cur_pos) <= i + 2 or restrict:
            calc_walk_restrictions(cur_pos, body_dir)
            restrict = True
        cur_pos = moved_pos(cur_pos, body_dir)
    edges = [((i, j), d) for i in range(N//2) for j in range(N//2) for d in range(4) if in_bounds(moved_pos((i, j), d), N//2)]
    uf = UnionFind((N//2) * (N//2))
    inv_uf = UnionFind((N//2+1) * (N//2+1))
    for i in range(N//2):
        inv_uf.union(i*(N//2+1)+0, (i+1)*(N//2+1)+0)
        inv_uf.union(i*(N//2+1)+(N//2), (i+1)*(N//2+1)+(N//2))
        inv_uf.union(0*(N//2+1)+i, 0*(N//2+1)+(i+1))
        inv_uf.union((N//2)*(N//2+1)+i, (N//2)*(N//2+1)+(i+1))
    def calc_inv_pos(pos, dir):
        if dir == North:
            return ((pos[0], pos[1]+1), (pos[0]+1, pos[1]+1))
        if dir == East:
            return ((pos[0]+1, pos[1]), (pos[0]+1, pos[1]+1))
        if dir == South:
            return ((pos[0], pos[1]), (pos[0]+1, pos[1]))
        if dir == West:
            return ((pos[0], pos[1]), (pos[0], pos[1]+1))
    for pos, dir in edges:
        if tree[pos][dir] == MUST:
            nxt = moved_pos(pos, dir)
            uf.union(pos[0]*(N//2)+pos[1], nxt[0]*(N//2)+nxt[1])
        if tree[pos][dir] == FORBIDDEN:
            pos, nxt = calc_inv_pos(pos, dir)
            inv_uf.union(pos[0]*(N//2+1)+pos[1], nxt[0]*(N//2+1)+nxt[1])
    initial_uf = uf.copy()
    initial_inv_uf = inv_uf.copy()
    intial_tree = {k: v[:] for k, v in tree.items()}
    def undo_to_initial():
        global tree
        nonlocal uf, inv_uf
        uf = initial_uf.copy()
        inv_uf = initial_inv_uf.copy()
        tree = {k: v[:] for k, v in intial_tree.items()}
    def set_tree_restriction(tree_pos, dir, restriction):
        opposite = moved_pos(tree_pos, dir)
        tree[tree_pos][dir] = restriction
        tree[opposite][(dir+2)%4] = restriction
    def can_move(pos, dir):
        nxt = moved_pos(pos, dir)
        tree_cur = (pos[0] // 2, pos[1] // 2)
        tree_nxt = (nxt[0] // 2, nxt[1] // 2)
        if tree_cur == tree_nxt:
            if in_bounds(moved_pos(tree_cur, (dir+3)%4), N//2):
                a, b = calc_inv_pos(tree_cur, (dir+3)%4)
                return not (tree[tree_cur][(dir+3)%4] != FORBIDDEN and inv_uf.same(a[0]*(N//2+1)+a[1], b[0]*(N//2+1)+b[1])) and tree[tree_cur][(dir+3)%4] != MUST
            return True
        else:
            a, b = tree_cur, moved_pos(tree_cur, dir)
            return not (tree[tree_cur][dir] != MUST and uf.same(a[0]*(N//2)+a[1], b[0]*(N//2)+b[1])) and tree[tree_cur][dir] != FORBIDDEN
    def update_tree(pos, dir):
        nxt = moved_pos(pos, dir)
        tree_cur = (pos[0] // 2, pos[1] // 2)
        tree_nxt = (nxt[0] // 2, nxt[1] // 2)
        if tree_cur == tree_nxt:
            if in_bounds(moved_pos(tree_cur, (dir+3)%4), N//2):
                a, b = calc_inv_pos(tree_cur, (dir+3)%4)
                inv_uf.union(a[0]*(N//2+1)+a[1], b[0]*(N//2+1)+b[1])
                set_tree_restriction(tree_cur, (dir+3)%4, FORBIDDEN)
        else:
            a, b = tree_cur, moved_pos(tree_cur, dir)
            uf.union(a[0]*(N//2)+a[1], b[0]*(N//2)+b[1])
            set_tree_restriction(tree_cur, dir, MUST)

    best_path = None
    for v in range(8):
        pos = head_pos
        path_dirs = []
        while pos != apple_pos and (best_path is None or len(path_dirs) <= len(best_path)):
            cand_ds = []
            for d in range(4):
                next_pos = moved_pos(pos, d)
                if not in_bounds(next_pos, N):
                    continue
                if d in [[2, 0][pos[0] % 2], [1, 3][pos[1] % 2]]:
                    continue
                dist_diff = distance(next_pos, apple_pos) - distance(pos, apple_pos)
                cand_ds.append((dist_diff, (v%4+[d, -d][v//4])%4, d))
            for _, _, d in sorted(cand_ds):
                if can_move(pos, d):
                    path_dirs.append(d)
                    update_tree(pos, d)
                    pos = moved_pos(pos, d)
                    break
            else:
                raise
        undo_to_initial()
        if best_path is None or len(path_dirs) < len(best_path):
            best_path = path_dirs
    pos = head_pos
    for d in best_path:
        update_tree(pos, d)
        pos = moved_pos(pos, d)
    return best_path

def fill_spanning_tree():
    global tree
    edges = [((i, j), d) for i in range(N//2) for j in range(N//2) for d in range(4) if in_bounds(moved_pos((i, j), d), N//2)]
    uf = UnionFind((N//2) * (N//2))
    for pos, dir in edges:
        if tree[pos][dir] == MUST:
            nxt = moved_pos(pos, dir)
            uf.union(pos[0]*(N//2)+pos[1], nxt[0]*(N//2)+nxt[1])
    for pos, dir in edges:
        if tree[pos][dir] != FREE:
            continue
        nxt = moved_pos(pos, dir)
        if uf.find(pos[0]*(N//2)+pos[1]) != uf.find(nxt[0]*(N//2)+nxt[1]):
            set_tree_restriction(pos, dir, MUST)
            uf.union(pos[0]*(N//2)+pos[1], nxt[0]*(N//2)+nxt[1])
    for pos, dir in edges:
        if tree[pos][dir] == FREE:
            set_tree_restriction(pos, dir, FORBIDDEN)

def calc_hamilton_cycle():
    global hamilton_cycle
    hamilton_cycle = {}
    pos = (0, 0)
    prev_dir = West
    for _ in range(N * N):
        next_dir = None
        tree_pos = (pos[0] // 2, pos[1] // 2)
        restrictions = tree[tree_pos]
        nei = set()
        if (pos[0] % 2, pos[1] % 2) == (0, 0):
            nei.add(South if restrictions[South] == MUST else East)
            nei.add(West if restrictions[West] == MUST else North)
        if (pos[0] % 2, pos[1] % 2) == (0, 1):
            nei.add(North if restrictions[North] == MUST else East)
            nei.add(West if restrictions[West] == MUST else South)
        if (pos[0] % 2, pos[1] % 2) == (1, 0):
            nei.add(East if restrictions[East] == MUST else North)
            nei.add(South if restrictions[South] == MUST else West)
        if (pos[0] % 2, pos[1] % 2) == (1, 1):
            nei.add(East if restrictions[East] == MUST else South)
            nei.add(North if restrictions[North] == MUST else West)
        next_dir, = nei - {(prev_dir+2)%4}
        hamilton_cycle[pos] = next_dir
        pos = moved_pos(pos, next_dir)
        prev_dir = next_dir

apple_pos = measure()
while length < N * N:
    if head_pos == apple_pos:
        apple_pos = measure()
    tree = {(i, j): [FREE if in_bounds(moved_pos((i, j), d), N//2) else FORBIDDEN for d in range(4)] for i in range(N//2) for j in range(N//2)}
    hamilton_cycle = {}
    apple_path = calc_shortest_path()
    fill_spanning_tree()
    calc_hamilton_cycle()
    for _ in range(16 if len(apple_path) >= 120 else len(apple_path)):
        if head_pos == apple_pos:
            break
        next_dir = hamilton_cycle[head_pos]
        do_move(next_dir)
