"""技能系统"""
from dataclasses import dataclass, field

GCD_DURATION = 1.5       # 公共冷却时长
CANCEL_LOCKOUT = 0.5     # 取消施法硬直
INTERRUPT_LOCKOUT = 0.5  # 引导被打断后的硬直

# 效果阶段: 前置 -> 主要 -> 后置
_PHASE_ORDER = {"pre": 0, "main": 1, "post": 2}


@dataclass
class Effect:
    """技能效果。phase 控制执行阶段(pre/main/post), order 控制同阶段内顺序。"""
    name: str
    apply: object = None
    phase: str = "main"
    order: int = 0

    def __call__(self):
        if callable(self.apply):
            self.apply()


@dataclass
class Skill:
    sid: str
    name: str
    cooldown: float
    mana_cost: float
    damage: float
    gcd: bool = True
    channel_time: float = 0
    effects: list = field(default_factory=list)
    range: float = 0.0
    level: int = 1
    # 每级成长系数
    damage_growth: float = 1.2
    cooldown_growth: float = 0.9
    mana_growth: float = 1.1
    range_growth: float = 1.05

    def __post_init__(self):
        self.base_damage = self.damage
        self.base_cooldown = self.cooldown
        self.base_mana_cost = self.mana_cost
        self.base_range = self.range


def _sweep_circle(start, delta, circle, radius):
    """线段(带半径)与圆的扫掠检测, 返回最早碰撞参数 t∈[0,1], 无碰撞返回 None。"""
    ox, oy, oradius = circle
    r = oradius + radius
    fx, fy = start[0] - ox, start[1] - oy
    dx, dy = delta
    a = dx * dx + dy * dy
    if a == 0:
        return 0.0 if fx * fx + fy * fy <= r * r else None
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    sqrt_disc = disc ** 0.5
    t = (-b - sqrt_disc) / (2 * a)
    if 0.0 <= t <= 1.0:
        return t
    return None


class SkillSystem:
    def __init__(self):
        self.skills: dict[str, Skill] = {}
        self.cooldowns: dict[str, float] = {}   # 各技能独立冷却
        self.gcd_remaining = 0.0                # 公共冷却, 与独立冷却分开计时
        self.mana = 100.0
        self.casting = None
        self.channel_remaining = 0.0
        self.interrupted = 0.0              # 打断状态剩余时间
        self.cancel_cd = 0.0                # 取消施法硬直

    def cast(self, sid: str):
        skill = self.skills[sid]
        if self.cancel_cd > 0 or self.interrupted > 0:
            return False
        if self.casting is not None:
            return False
        if self.cooldowns.get(sid, 0) > 0:
            return False
        if skill.gcd and self.gcd_remaining > 0:
            return False
        if self.mana < skill.mana_cost:
            return False
        self.mana -= skill.mana_cost
        # 只触发本技能的独立冷却; 公共冷却仅由 gcd 技能触发
        self.cooldowns[sid] = skill.cooldown
        if skill.gcd:
            self.gcd_remaining = GCD_DURATION
        if skill.channel_time > 0:
            self.casting = sid
            self.channel_remaining = skill.channel_time
        else:
            self._apply_effects(skill)
        return True

    def tick(self, dt):
        for sid in list(self.cooldowns.keys()):
            self.cooldowns[sid] -= dt
            if self.cooldowns[sid] <= 0:
                del self.cooldowns[sid]
        self.gcd_remaining = max(0.0, self.gcd_remaining - dt)
        self.cancel_cd = max(0.0, self.cancel_cd - dt)
        self.interrupted = max(0.0, self.interrupted - dt)
        if self.casting is not None:
            self.channel_remaining -= dt
            if self.channel_remaining <= 0:
                skill = self.skills[self.casting]
                self.casting = None
                self.channel_remaining = 0.0
                self._apply_effects(skill)

    def cancel_cast(self):
        # 取消施法: 停止当前动作并进入短暂取消硬直, 硬直期间不能重新施法
        self.casting = None
        self.channel_remaining = 0.0
        self.cancel_cd = CANCEL_LOCKOUT
        return True

    def interrupt(self):
        """引导被打断: 按剩余引导时间比例返还冷却, 并进入打断状态。"""
        if self.casting is None:
            return False
        skill = self.skills[self.casting]
        if skill.channel_time > 0:
            ratio = max(0.0, self.channel_remaining) / skill.channel_time
            left = self.cooldowns.get(skill.sid, 0.0) - skill.cooldown * ratio
            if left > 0:
                self.cooldowns[skill.sid] = left
            else:
                self.cooldowns.pop(skill.sid, None)
        self.casting = None
        self.channel_remaining = 0.0
        self.interrupted = INTERRUPT_LOCKOUT
        return True

    def upgrade(self, sid: str):
        """升级: 伤害/冷却/消耗/范围全部按等级缩放。"""
        skill = self.skills[sid]
        skill.level += 1
        n = skill.level - 1
        skill.damage = skill.base_damage * skill.damage_growth ** n
        skill.cooldown = skill.base_cooldown * skill.cooldown_growth ** n
        skill.mana_cost = skill.base_mana_cost * skill.mana_growth ** n
        skill.range = skill.base_range * skill.range_growth ** n
        return skill

    def dash(self, sid: str, start, end, obstacles=(), radius=0.0):
        """位移技能: 沿路径扫掠检测碰撞, 返回实际到达点(不会穿墙)。"""
        skill = self.skills[sid]
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        dist = (dx * dx + dy * dy) ** 0.5
        if skill.range > 0 and dist > skill.range:
            scale = skill.range / dist
            dx, dy = dx * scale, dy * scale
        t_hit = 1.0
        for obs in obstacles:
            t = _sweep_circle((sx, sy), (dx, dy), obs, radius)
            if t is not None and t < t_hit:
                t_hit = t
        return (sx + dx * t_hit, sy + dy * t_hit)

    @staticmethod
    def _ordered_effects(skill):
        def sort_key(item):
            index, eff = item
            phase = getattr(eff, "phase", "main")
            order = getattr(eff, "order", 0)
            return (_PHASE_ORDER.get(phase, 1), order, index)
        return [eff for _, eff in sorted(enumerate(skill.effects), key=sort_key)]

    def _apply_effects(self, skill):
        for eff in self._ordered_effects(skill):
            eff()
