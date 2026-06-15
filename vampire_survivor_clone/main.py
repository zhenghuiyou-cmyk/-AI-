"""
吸血鬼幸存者风格小游戏 —— 护身盾旋转攻击
使用 WASD 移动，环绕物自动杀敌
"""

import pygame
import math
import random
import sys

# ==================== 初始化 ====================
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("吸血鬼幸存者 - 护身盾版")
clock = pygame.time.Clock()
font = pygame.font.SysFont("microsoftyahei", 20)

# 颜色常量
COLOR_BG       = (20, 20, 40)
COLOR_PLAYER   = (50, 220, 80)
COLOR_ENEMY    = (220, 50, 50)
COLOR_ORBITER  = (255, 220, 50)
COLOR_TRAIL    = (80, 80, 120)
COLOR_UI       = (220, 220, 220)

# ==================== 游戏状态 ====================
score = 0
lives = 5
game_over = False
spawn_timer = 0
upgrade_timer = 0          # 每30秒升级计时
orbiter_base_speed = 3.0   # 环绕物基础角速度 (弧度/秒)
enemy_base_speed = 1.8     # 敌人基础移动速度

# ==================== 玩家类 ====================
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 18
        self.speed = 200       # 每秒移动像素
        self.knockback_cooldown = 0  # 击退无敌帧
        self.orbiters = []     # 环绕物列表

    def add_orbiter(self):
        """添加一个环绕物，初始角度随机分布"""
        n = len(self.orbiters)
        angle = (math.pi * 2 / (n + 1)) * n   # 均分角度
        self.orbiters.append({
            "angle": angle,
            "distance": 60,                    # 环绕半径
            "radius": 6,
            "speed": orbiter_base_speed,
        })

    def update(self, dt, keys):
        """每帧更新：处理移动 + 环绕物旋转 + 击退冷却"""
        # ---- WASD 移动 ----
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1

        # 归一化对角移动
        if dx != 0 or dy != 0:
            length = math.sqrt(dx * dx + dy * dy)
            dx, dy = dx / length, dy / length

        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt

        # 边界限制
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(HEIGHT - self.radius, self.y))

        # ---- 环绕物旋转 ----
        for ob in self.orbiters:
            ob["angle"] += ob["speed"] * dt
            ob["angle"] %= math.pi * 2   # 角度保持在 [0, 2π)

        # ---- 击退无敌帧递减 ----
        if self.knockback_cooldown > 0:
            self.knockback_cooldown -= dt

    def apply_knockback(self, dx, dy):
        """给玩家施加击退，并进入短暂无敌状态"""
        self.x += dx
        self.y += dy
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(HEIGHT - self.radius, self.y))
        self.knockback_cooldown = 0.5   # 0.5秒无敌

    def get_orbiter_positions(self):
        """返回所有环绕物当前的世界坐标"""
        positions = []
        for ob in self.orbiters:
            ox = self.x + math.cos(ob["angle"]) * ob["distance"]
            oy = self.y + math.sin(ob["angle"]) * ob["distance"]
            positions.append((ox, oy, ob["radius"]))
        return positions

    def draw(self, surface):
        """绘制玩家（绿色圆）和环绕物（黄色小圆 + 轨迹虚线）"""
        # 玩家本体
        pygame.draw.circle(surface, COLOR_PLAYER, (int(self.x), int(self.y)), self.radius)
        # 玩家外圈光晕
        pygame.draw.circle(surface, (100, 255, 140), (int(self.x), int(self.y)), self.radius + 2, 2)

        # 环绕物 + 轨迹
        for ob in self.orbiters:
            ox = int(self.x + math.cos(ob["angle"]) * ob["distance"])
            oy = int(self.y + math.sin(ob["angle"]) * ob["distance"])

            # 绘制旋转轨迹（虚线圆）
            pygame.draw.circle(surface, COLOR_TRAIL,
                               (int(self.x), int(self.y)),
                               int(ob["distance"]), 1)

            # 环绕物本体（黄色小圆）
            pygame.draw.circle(surface, COLOR_ORBITER, (ox, oy), ob["radius"])
            # 环绕物光晕
            pygame.draw.circle(surface, (255, 240, 120), (ox, oy), ob["radius"] + 1, 1)


# ==================== 敌人类 ====================
class Enemy:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 14
        self.speed = enemy_base_speed + random.uniform(-0.3, 0.3)

    def update(self, dt, px, py):
        """向玩家方向移动"""
        dx = px - self.x
        dy = py - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            dx, dy = dx / dist, dy / dist
        self.x += dx * self.speed * 60 * dt
        self.y += dy * self.speed * 60 * dt

    def is_offscreen(self):
        """超出屏幕边界一定范围则标记清理"""
        margin = 60
        return (self.x < -margin or self.x > WIDTH + margin or
                self.y < -margin or self.y > HEIGHT + margin)

    def draw(self, surface):
        pygame.draw.circle(surface, COLOR_ENEMY, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 100, 100), (int(self.x), int(self.y)), self.radius, 2)


# ==================== 辅助函数 ====================
def circles_collide(x1, y1, r1, x2, y2, r2):
    """两个圆是否碰撞"""
    dist = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    return dist < r1 + r2

def spawn_enemy():
    """在屏幕四条边随机位置生成敌人"""
    side = random.randint(0, 3)
    margin = 40
    if side == 0:  # 上边
        return Enemy(random.randint(0, WIDTH), -margin)
    elif side == 1:  # 右边
        return Enemy(WIDTH + margin, random.randint(0, HEIGHT))
    elif side == 2:  # 下边
        return Enemy(random.randint(0, WIDTH), HEIGHT + margin)
    else:            # 左边
        return Enemy(-margin, random.randint(0, HEIGHT))

def draw_ui():
    """绘制得分、生命、波次时间"""
    texts = [
        f"得分: {score}",
        f"生命: {'♥' * lives}{'♡' * (5 - lives)}",
        f"环绕物数量: {len(player.orbiters)}",
        f"下次升级: {max(0, 30 - int(upgrade_timer))} 秒",
    ]
    y_offset = 10
    for text in texts:
        surf = font.render(text, True, COLOR_UI)
        screen.blit(surf, (10, y_offset))
        y_offset += 26

    # 游戏结束提示
    if game_over:
        over_text = font.render("游戏结束！按 R 重新开始", True, (255, 80, 80))
        over_rect = over_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(over_text, over_rect)


# ==================== 初始化游戏 ====================
player = Player(WIDTH // 2, HEIGHT // 2)
player.add_orbiter()  # 初始1个环绕物
enemies = []


# ==================== 主循环 ====================
running = True
while running:
    dt = clock.tick(60) / 1000.0   # 秒为单位，上限60fps
    dt = min(dt, 0.05)             # 防止卡顿时跳跃过大

    # ---- 事件处理 ----
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_r and game_over:
                # 重新开始
                score = 0
                lives = 5
                game_over = False
                spawn_timer = 0
                upgrade_timer = 0
                orbiter_base_speed = 3.0
                enemy_base_speed = 1.8
                player = Player(WIDTH // 2, HEIGHT // 2)
                player.add_orbiter()
                enemies = []

    if game_over:
        # 游戏结束后只绘制，不更新逻辑
        screen.fill(COLOR_BG)
        for e in enemies:
            e.draw(screen)
        player.draw(screen)
        draw_ui()
        pygame.display.flip()
        continue

    # ---- 输入 ----
    keys = pygame.key.get_pressed()
    player.update(dt, keys)

    # ---- 定时升级（每30秒） ----
    upgrade_timer += dt
    if upgrade_timer >= 30:
        upgrade_timer = 0
        if len(player.orbiters) < 3:
            player.add_orbiter()
        orbiter_base_speed += 0.5          # 环绕物转速加快
        enemy_base_speed += 0.2            # 敌人也变快，增加难度

    # ---- 敌人生成 ----
    spawn_timer += dt
    spawn_interval = max(0.3, 1.2 - len(player.orbiters) * 0.15)  # 环绕物越多，敌人刷越快
    if spawn_timer >= spawn_interval:
        spawn_timer = 0
        enemies.append(spawn_enemy())

    # ---- 敌人移动 + 碰撞检测 ----
    enemies_to_remove = []
    orbiter_positions = player.get_orbiter_positions()

    for i, enemy in enumerate(enemies):
        enemy.update(dt, player.x, player.y)

        # ==== 环绕物 vs 敌人 ====
        for ox, oy, orad in orbiter_positions:
            if circles_collide(ox, oy, orad, enemy.x, enemy.y, enemy.radius):
                enemies_to_remove.append(i)
                score += 10
                break   # 一个敌人只被一个环绕物击杀
        else:
            # ==== 玩家 vs 敌人 ====
            if (player.knockback_cooldown <= 0 and
                circles_collide(player.x, player.y, player.radius,
                                enemy.x, enemy.y, enemy.radius)):
                enemies_to_remove.append(i)
                lives -= 1
                # 击退方向：从敌人指向玩家
                dx = player.x - enemy.x
                dy = player.y - enemy.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    dx, dy = dx / dist * 60, dy / dist * 60
                player.apply_knockback(dx, dy)

                if lives <= 0:
                    game_over = True
                break

    # 移除被击杀的敌人
    for idx in sorted(set(enemies_to_remove), reverse=True):
        if idx < len(enemies):
            enemies.pop(idx)

    # 清理离屏敌人
    enemies = [e for e in enemies if not e.is_offscreen()]

    # ---- 绘制 ----
    screen.fill(COLOR_BG)

    # 轨迹先于玩家绘制（在下方）
    enemies.sort(key=lambda e: e.y)   # 简单的深度排序
    for e in enemies:
        e.draw(screen)

    player.draw(screen)
    draw_ui()

    pygame.display.flip()

pygame.quit()
sys.exit()
