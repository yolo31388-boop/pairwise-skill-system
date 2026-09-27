"""技能系统测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import SkillSystem, Skill

class TestCooldown:
    def test_gcd_and_independent_separate(self):
        ss = SkillSystem()
        ss.skills["a"] = Skill("a", "A", 5, 10, 100, gcd=True)
        ss.skills["b"] = Skill("b", "B", 3, 10, 100, gcd=True)
        ss.cast("a")
        assert ss.cooldowns.get("a", 0) > 0
        # b的独立冷却不应被a触发
        assert ss.cooldowns.get("b", 0) == 0

class TestCancel:
    def test_cancel_enters_cd(self):
        ss = SkillSystem()
        ss.skills["a"] = Skill("a", "A", 5, 10, 100, channel_time=2)
        ss.cast("a")
        ss.cancel_cast()
        assert ss.cancel_cd > 0 or ss.cooldowns.get("a", 0) > 0, "取消施法无冷却"
