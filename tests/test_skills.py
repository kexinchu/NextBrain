from autoresearch.skills import BUILTIN_SKILLS, list_skills, load_skill


def test_all_builtin_skills_are_packaged() -> None:
    loaded = list_skills()
    assert [skill.name for skill in loaded] == list(BUILTIN_SKILLS)
    assert all(skill.description and skill.body for skill in loaded)


def test_unknown_skill_fails() -> None:
    try:
        load_skill("not-real")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown skill should fail")


def test_skills_are_host_model_native() -> None:
    for skill in list_skills():
        assert "autoresearch run" in skill.body
        assert any(word in skill.body for word in ("Do not", "do not", "Never", "never"))
