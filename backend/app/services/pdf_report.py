"""Phase 9: the admin-generated per-student PDF report -- branded, RTL, Arabic-shaped (spec:
"professionally designed PDF containing the academy name, logo, student information, attendance,
exam performance, points, completed lessons, and totals within the selected period"). Built with
reportlab/Platypus rather than WeasyPrint: no native Cairo/Pango system libraries to install, which
matters both for the slim Docker image and for running this same code outside Docker.

Arabic text needs two passes before reportlab can lay it out correctly, neither of which reportlab
does on its own: arabic_reshaper joins each letter into its correct presentation form (a letter
drawn in isolation looks wrong in Arabic), and python-bidi reorders the shaped text into visual
(left-to-right-storage) order for the renderer. Skipping either pass produces disconnected,
right-to-left-stored glyphs that read backwards.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.reports import StudentPeriodReport

_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoNaskhArabic-Regular.ttf"
_FONT_NAME = "NotoNaskh"
_PRIMARY = colors.HexColor("#1A5AD9")
_BORDER = colors.HexColor("#E2E2E2")
_ZEBRA = colors.HexColor("#F7F7F8")
_font_registered = False


def _ensure_font() -> None:
    global _font_registered
    if not _font_registered:
        pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT_PATH)))
        _font_registered = True


def _rtl(text: object) -> str:
    text = str(text or "")
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(text))


def _style(size: int = 10, bold: bool = False, color=colors.black, align=TA_RIGHT) -> ParagraphStyle:
    return ParagraphStyle(name=f"s{size}-{bold}-{align}-{color}", fontName=_FONT_NAME, fontSize=size, leading=size * 1.45, textColor=color, alignment=align)


def _p(text: object, *, size: int = 10, bold: bool = False, color=colors.black, align=TA_RIGHT) -> Paragraph:
    return Paragraph(_rtl(text), _style(size=size, bold=bold, color=color, align=align))


def _date_range_text(date_from: datetime | None, date_to: datetime | None) -> str:
    if not date_from and not date_to:
        return "كل الفترة"
    if date_from and date_to:
        return f"{date_from.strftime('%Y-%m-%d')} — {date_to.strftime('%Y-%m-%d')}"
    if date_from:
        return f"من {date_from.strftime('%Y-%m-%d')}"
    return f"حتى {date_to.strftime('%Y-%m-%d')}"  # type: ignore[union-attr]


def _bordered_table_style(*, header: bool) -> TableStyle:
    rules = [
        ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if header:
        rules += [
            ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ZEBRA]),
        ]
    return TableStyle(rules)


def _section(story: list, title: str) -> None:
    story.append(Spacer(1, 6 * mm))
    story.append(_p(title, size=13, bold=True, color=_PRIMARY, align=TA_RIGHT))
    story.append(Spacer(1, 2 * mm))


def build_student_period_pdf(report: StudentPeriodReport, *, academy_name: str, logo_bytes: bytes | None = None) -> bytes:
    _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm)
    story: list = []

    if logo_bytes:
        try:
            img = Image(io.BytesIO(logo_bytes), width=20 * mm, height=20 * mm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 3 * mm))
        except Exception:  # noqa: BLE001 — a broken/unsupported logo image must never break the report
            pass

    story.append(_p(academy_name, size=17, bold=True, color=_PRIMARY, align=TA_CENTER))
    story.append(_p("تقرير أداء الطالب", size=12, bold=True, align=TA_CENTER))
    story.append(_p(_date_range_text(report.period.date_from, report.period.date_to), size=9, color=colors.grey, align=TA_CENTER))
    story.append(Spacer(1, 6 * mm))

    info_rows = [
        [_p("الاسم", size=9, bold=True), _p(report.student.full_name, size=10)],
        [_p("كود الطالب", size=9, bold=True), _p(report.student.student_code or "-", size=10)],
        [_p("الصف", size=9, bold=True), _p(report.student.grade_level or "-", size=10)],
        [_p("نوع الاشتراك", size=9, bold=True), _p(report.student.effective_subscription, size=10)],
    ]
    info_table = Table(info_rows, colWidths=[45 * mm, 115 * mm])
    info_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, _BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.6, _BORDER),
        ("BACKGROUND", (0, 0), (0, -1), _ZEBRA), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)

    exams_count = len(report.exams)
    avg_exam = round(sum(e.percentage for e in report.exams) / exams_count) if exams_count else 0
    totals_rows = [
        [_p("نسبة الحضور", size=9, bold=True, align=TA_CENTER), _p("متوسط الامتحانات", size=9, bold=True, align=TA_CENTER), _p("دروس مكتملة", size=9, bold=True, align=TA_CENTER), _p("إجمالي النقاط", size=9, bold=True, align=TA_CENTER)],
        [_p(f"{report.attendance.rate}%", size=14, bold=True, align=TA_CENTER), _p(f"{avg_exam}%", size=14, bold=True, align=TA_CENTER), _p(str(len(report.completed_lessons)), size=14, bold=True, align=TA_CENTER), _p(str(report.points_total), size=14, bold=True, align=TA_CENTER)],
    ]
    totals_table = Table(totals_rows, colWidths=[40 * mm] * 4)
    totals_table.setStyle(_bordered_table_style(header=True))
    story.append(Spacer(1, 4 * mm))
    story.append(totals_table)

    _section(story, "الحضور")
    att = report.attendance
    att_rows = [
        [_p("حاضر", size=9, bold=True, align=TA_CENTER), _p("متأخر", size=9, bold=True, align=TA_CENTER), _p("غائب", size=9, bold=True, align=TA_CENTER), _p("بعذر", size=9, bold=True, align=TA_CENTER)],
        [_p(str(att.present), size=10, align=TA_CENTER), _p(str(att.late), size=10, align=TA_CENTER), _p(str(att.absent), size=10, align=TA_CENTER), _p(str(att.excused), size=10, align=TA_CENTER)],
    ]
    att_table = Table(att_rows, colWidths=[40 * mm] * 4)
    att_table.setStyle(_bordered_table_style(header=True))
    story.append(att_table)

    _section(story, "نتائج الامتحانات")
    if report.exams:
        exam_rows = [[_p("الامتحان", size=9, bold=True), _p("النسبة", size=9, bold=True, align=TA_CENTER), _p("النتيجة", size=9, bold=True, align=TA_CENTER), _p("التاريخ", size=9, bold=True, align=TA_CENTER)]]
        for e in report.exams:
            exam_rows.append([
                _p(e.exam_title, size=9), _p(f"{e.percentage}%", size=9, align=TA_CENTER),
                _p("ناجح" if e.passed else "راسب", size=9, color=colors.HexColor("#15803D") if e.passed else colors.HexColor("#B42318"), align=TA_CENTER),
                _p(e.submitted_at.strftime("%Y-%m-%d") if e.submitted_at else "-", size=9, align=TA_CENTER),
            ])
        exam_table = Table(exam_rows, colWidths=[80 * mm, 30 * mm, 30 * mm, 30 * mm], repeatRows=1)
        exam_table.setStyle(_bordered_table_style(header=True))
        story.append(exam_table)
    else:
        story.append(_p("لا يوجد امتحانات في هذه الفترة", size=9, color=colors.grey))

    _section(story, "الدروس المكتملة")
    if report.completed_lessons:
        lesson_rows = [[_p("الدرس", size=9, bold=True), _p("الكورس", size=9, bold=True), _p("تاريخ الإكمال", size=9, bold=True, align=TA_CENTER)]]
        shown = report.completed_lessons[:60]
        for lesson in shown:
            lesson_rows.append([_p(lesson.lesson_title, size=9), _p(lesson.course_title, size=9), _p(lesson.completed_at.strftime("%Y-%m-%d"), size=9, align=TA_CENTER)])
        lesson_table = Table(lesson_rows, colWidths=[70 * mm, 60 * mm, 40 * mm], repeatRows=1)
        lesson_table.setStyle(_bordered_table_style(header=True))
        story.append(lesson_table)
        if len(report.completed_lessons) > len(shown):
            story.append(Spacer(1, 2 * mm))
            story.append(_p(f"+ {len(report.completed_lessons) - len(shown)} درس إضافي", size=8, color=colors.grey))
    else:
        story.append(_p("لا يوجد دروس مكتملة في هذه الفترة", size=9, color=colors.grey))

    _section(story, "سجل النقاط")
    if report.points_events:
        point_rows = [[_p("الوصف", size=9, bold=True), _p("الكورس", size=9, bold=True), _p("النقاط", size=9, bold=True, align=TA_CENTER), _p("التاريخ", size=9, bold=True, align=TA_CENTER)]]
        shown_points = report.points_events[:60]
        for point in shown_points:
            point_rows.append([
                _p(point.description, size=9), _p(point.course_title or "-", size=9),
                _p(f"+{point.points}" if point.points >= 0 else str(point.points), size=9, align=TA_CENTER),
                _p(point.created_at.strftime("%Y-%m-%d"), size=9, align=TA_CENTER),
            ])
        point_table = Table(point_rows, colWidths=[60 * mm, 40 * mm, 20 * mm, 30 * mm], repeatRows=1)
        point_table.setStyle(_bordered_table_style(header=True))
        story.append(point_table)
        if len(report.points_events) > len(shown_points):
            story.append(Spacer(1, 2 * mm))
            story.append(_p(f"+ {len(report.points_events) - len(shown_points)} حركة نقاط إضافية", size=8, color=colors.grey))
    else:
        story.append(_p("لا يوجد نقاط في هذه الفترة", size=9, color=colors.grey))

    if report.admin_notes:
        _section(story, "ملاحظات الإدارة")
        story.append(_p(report.admin_notes, size=9))

    def _footer(canvas, doc_) -> None:
        canvas.saveState()
        canvas.setFont(_FONT_NAME, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, _rtl(f"{academy_name} — صفحة {doc_.page}"))
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
