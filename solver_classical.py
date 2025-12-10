North = 0
East = 1
South = 2
West = 3

x = 0
y = 0
n = 32
cnt = 0
nx, ny = measure()

def mov(d):
    global x
    global y
    global nx
    global ny
    global cnt
    if cnt < n * n - 1:
        if d == North:
            y += 1
        elif d == East:
            x += 1
        elif d == South:
            y -= 1
        elif d == West:
            x -= 1
        move(d)
        if (x, y) == (nx, ny):
            cnt += 1
            if cnt < n * n - 2:
                nx, ny = measure()
while cnt < n * n - 2:
    for i in range(n-1):
        mov(North)
    mov(East)
    for j in range(n // 2 - 1):
        go = 0
        if cnt >= (n - 1) * 4 + x // 2 * (n - 2) * 2 - 1 or cnt >= n * n // 2:
            go = n-2
        elif x <= nx < x + 2 and 0 < ny < n-1:
            go = n-1-ny
        for i in range(go):
            mov(South)
        mov(East)
        for i in range(go):
            mov(North)
        mov(East)
    for i in range(n-1):
        mov(South)
    for i in range(n-1):
        mov(West)