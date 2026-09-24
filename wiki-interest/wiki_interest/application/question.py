"""The question to the user when an edition has no article, composed by the code.

The agent used to write this question itself and a cheap model drifted: it answered a
Russian user in Ukrainian after reading Ukrainian article titles, or chose a substitute
for the user. Now the code lays the question out from the options it found and the agent
sends it word for word, as it does with the chat answer. For a language without a catalog
the agent first translates the few labels the question uses (``render.py --ui``); they are
kept for the session, so the report later reuses them.
"""

from __future__ import annotations

from collections.abc import Mapping
from string import Formatter

from wiki_interest.contracts.summary import Clarification, CoverageOptionOut
from wiki_interest.i18n import Translator

__all__ = ["compose_question", "label_problems", "option_text"]


def option_text(option: CoverageOptionOut, project: str, t: Translator) -> str:
    """One option in a sentence: the page with its link and views, or leaving it out."""
    if option.kind == "skip" or option.title is None:
        return t.t("option.skip", project=project)
    views = t.number(option.views_avg) if option.views_avg is not None else t.t("value.na")
    section = t.t("option.section", section=option.section) if option.section else ""
    text = t.t(
        f"option.{option.kind}",
        title=option.title,
        target=option.target or "",
        section=section,
        views=views,
        url=option.url or "",
    )
    if option.snippet:
        text += " " + t.t("option.snippet", snippet=option.snippet)
    return text


def compose_question(clarification: Clarification, t: Translator) -> str:
    """The message that asks the user what to measure where an edition has no article.

    Per topic, which item it is (the user can catch a wrong one before choosing); per
    edition, that it has no article, the numbered options with their links, and a request
    for the topic's local name when none was known to search for; then the question.
    """
    lines: list[str] = []
    named: set[str] = set()
    for gap in clarification.gaps:
        if gap.topic_id not in named and gap.qid is not None:
            named.add(gap.topic_id)
            description = (
                t.t("gap.entity_description", description=gap.description)
                if gap.description
                else ""
            )
            label = gap.label or gap.query
            lines += [t.t("summary.topic_line", label=label, description=description, qid=gap.qid)]
            lines += [""]
        lines.append(t.t("gap.question", project=gap.project, topic=gap.label or gap.query))
        kinds = {option.kind for option in gap.options}
        if kinds & {"redirect", "broader"}:
            lines.append(t.t("gap.broader_intro"))
        elif "mention" in kinds:
            lines.append(t.t("gap.mention_intro"))
        lines += ["", *(f"{o.number}. {option_text(o, gap.project, t)}" for o in gap.options)]
        if not gap.terms:
            lines += ["", t.t("ask.local_name", project=gap.project)]
        lines.append("")
    projects = ", ".join(dict.fromkeys(gap.project for gap in clarification.gaps))
    lines.append(t.t("ask.which", projects=projects))
    return "\n".join(lines).strip()


def label_problems(asked: Mapping[str, str], given: Mapping[str, str]) -> list[str]:
    """What is wrong with the agent's translation of the labels it was asked for.

    Args:
        asked: ``key: English template`` the run asked to translate.
        given: The agent's ``key: translation``.

    Returns:
        One message per missing label or per placeholder a translation lost; empty if fine.
    """
    problems: list[str] = []
    for key, english in asked.items():
        text = given.get(key, "").strip()
        if not text:
            problems.append(f"ui.{key}: missing; translate {english!r}")
            continue
        lost = _fields(english) - _fields(text)
        if lost:
            names = ", ".join("{" + name + "}" for name in sorted(lost))
            problems.append(f"ui.{key}: keep the placeholders {names} as they are")
    return problems


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}
