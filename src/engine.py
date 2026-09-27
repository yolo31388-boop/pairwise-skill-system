"""技能系统 - 带6个bug"""
from dataclasses import dataclass, field
import time

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

class SkillSystem:
    def __init__(self):
        self.skills: dict[str, Skill] = {}
        self.cooldowns: dict[str, float] = {}  # bug1: 公共和独立冷却混用
        self.gcd_remaining = 0.0
        self.mana = 100.0
        self.casting = None
        self.cancel_cd = 0.0  # bug6: 取消无冷却

    def cast(self, sid: str):
        skill = self.skills[sid]
        if self.cooldowns.get(sid, 0) > 0:
            return False
        if skill.gcd and self.gcd_remaining > 0:
            return False
        if self.mana < skill.mana_cost:
            return False
        self.mana -= skill.mana_cost
        self.cooldowns[sid] = skill.cooldown  # bug1: 同时触发gcd
        self.gcd_remaining = 1.5
        # bug3: 效果按注册顺序
        for eff in skill.effects:
            eff()
        return True

    def tick(self, dt):
        for sid in list(self.cooldowns.keys()):
            self.cooldowns[sid] -= dt
            if self.cooldowns[sid] <= 0:
                del self.cooldowns[sid]
        self.gcd_remaining -= dt

    def cancel_cast(self):
        # bug6: 取消不进入冷却
        self.casting = None
        return True
