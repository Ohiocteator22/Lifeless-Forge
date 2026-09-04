# forge/templates.py
import xml.etree.ElementTree as ET
from pathlib import Path

def create_pptx_template(temp_dir, dummy_filename="media/dummy.bin"):
    (Path(temp_dir) / "ppt" / "media").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "ppt" / "_rels").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "ppt" / "slides").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "_rels").mkdir(parents=True, exist_ok=True)

    ct = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    ET.SubElement(ct, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(ct, "Default", Extension="bin", ContentType="application/vnd.ms-office.dummy")
    ET.SubElement(ct, "Override", PartName="/ppt/presentation.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")
    ET.SubElement(ct, "Override", PartName="/ppt/slides/slide1.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
    ET.SubElement(ct, "Override", PartName="/ppt/media/dummy.bin", ContentType="application/vnd.ms-office.dummy")
    (Path(temp_dir) / "[Content_Types].xml").write_text(ET.tostring(ct, encoding="unicode", xml_declaration=True))

    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="ppt/presentation.xml")
    (Path(temp_dir) / "_rels" / ".rels").write_text(ET.tostring(rels, encoding="unicode", xml_declaration=True))

    pres = ET.Element("presentation", attrib={
        "xmlns": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "xmlns:r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    })
    sldIdLst = ET.SubElement(pres, "sldIdLst")
    ET.SubElement(sldIdLst, "sldId", attrib={"Id": "256", "r:id": "rId1"})
    (Path(temp_dir) / "ppt" / "presentation.xml").write_text(ET.tostring(pres, encoding="unicode", xml_declaration=True))

    rels2 = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels2, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide", Target="slides/slide1.xml")
    (Path(temp_dir) / "ppt" / "_rels" / "presentation.xml.rels").write_text(ET.tostring(rels2, encoding="unicode", xml_declaration=True))

    slide = ET.Element("slide", xmlns="http://schemas.openxmlformats.org/presentationml/2006/main")
    cSld = ET.SubElement(slide, "cSld")
    spTree = ET.SubElement(cSld, "spTree")
    nvGrpSpPr = ET.SubElement(spTree, "nvGrpSpPr")
    ET.SubElement(nvGrpSpPr, "cNvPr", id="1", name="")
    ET.SubElement(nvGrpSpPr, "cNvGrpSpPr")
    ET.SubElement(nvGrpSpPr, "nvPr")
    ET.SubElement(spTree, "grpSpPr")
    sp = ET.SubElement(spTree, "sp")
    nvSpPr = ET.SubElement(sp, "nvSpPr")
    ET.SubElement(nvSpPr, "cNvPr", id="2", name="Dummy")
    ET.SubElement(nvSpPr, "cNvSpPr")
    ET.SubElement(nvSpPr, "nvPr")
    spPr = ET.SubElement(sp, "spPr")
    xfrm = ET.SubElement(spPr, "xfrm")
    ET.SubElement(xfrm, "off", x="0", y="0")
    ET.SubElement(xfrm, "ext", cx="0", cy="0")
    ET.SubElement(sp, "txBody")
    (Path(temp_dir) / "ppt" / "slides" / "slide1.xml").write_text(ET.tostring(slide, encoding="unicode", xml_declaration=True))

    return temp_dir

def create_docx_template(temp_dir, dummy_filename="word/media/dummy.bin"):
    (Path(temp_dir) / "word").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "word" / "_rels").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "_rels").mkdir(parents=True, exist_ok=True)

    ct = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    ET.SubElement(ct, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(ct, "Default", Extension="bin", ContentType="application/vnd.ms-office.dummy")
    ET.SubElement(ct, "Override", PartName="/word/document.xml", ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
    (Path(temp_dir) / "[Content_Types].xml").write_text(ET.tostring(ct, encoding="unicode", xml_declaration=True))

    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="word/document.xml")
    (Path(temp_dir) / "_rels" / ".rels").write_text(ET.tostring(rels, encoding="unicode", xml_declaration=True))

    doc = ET.Element("document", xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main")
    body = ET.SubElement(doc, "body")
    p = ET.SubElement(body, "p")
    r = ET.SubElement(p, "r")
    ET.SubElement(r, "t").text = "Dummy content"
    (Path(temp_dir) / "word" / "document.xml").write_text(ET.tostring(doc, encoding="unicode", xml_declaration=True))

    return temp_dir

def create_xlsx_template(temp_dir, dummy_filename="xl/media/dummy.bin"):
    (Path(temp_dir) / "xl" / "worksheets").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "xl" / "_rels").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "_rels").mkdir(parents=True, exist_ok=True)

    ct = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    ET.SubElement(ct, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(ct, "Default", Extension="bin", ContentType="application/vnd.ms-office.dummy")
    ET.SubElement(ct, "Override", PartName="/xl/workbook.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    ET.SubElement(ct, "Override", PartName="/xl/worksheets/sheet1.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    (Path(temp_dir) / "[Content_Types].xml").write_text(ET.tostring(ct, encoding="unicode", xml_declaration=True))

    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="xl/workbook.xml")
    (Path(temp_dir) / "_rels" / ".rels").write_text(ET.tostring(rels, encoding="unicode", xml_declaration=True))

    wb = ET.Element("workbook", xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    sheets = ET.SubElement(wb, "sheets")
    ET.SubElement(sheets, "sheet", attrib={"name": "Sheet1", "sheetId": "1", "r:id": "rId1"})
    (Path(temp_dir) / "xl" / "workbook.xml").write_text(ET.tostring(wb, encoding="unicode", xml_declaration=True))

    wb_rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(wb_rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", Target="worksheets/sheet1.xml")
    (Path(temp_dir) / "xl" / "_rels" / "workbook.xml.rels").write_text(ET.tostring(wb_rels, encoding="unicode", xml_declaration=True))

    sheet = ET.Element("worksheet", xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    sheetData = ET.SubElement(sheet, "sheetData")
    row = ET.SubElement(sheetData, "row", r="1")
    cell = ET.SubElement(row, "c", r="A1")
    ET.SubElement(cell, "v").text = "1"
    (Path(temp_dir) / "xl" / "worksheets" / "sheet1.xml").write_text(ET.tostring(sheet, encoding="unicode", xml_declaration=True))

    return temp_dir
