import logging
from string import Template
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path
from PIL import PpmImagePlugin
import pdf2image
import pytesseract
from typing import List
import google.auth
from google.cloud import translate_v2 as translate

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

TEXT_FILE_NAME_TEMPLATE = Template("$prefix-$lang-$page.txt")
LINE_ENDING = "\n"


@dataclass
class TextPage:
    lang: str
    page_number: str
    lines: List[str]
    path: Path

    def save_to_disk(self):
        self.path.write_text(LINE_ENDING.join(self.lines))


def convert_pdf_and_save_images(pdf_path: Path, output_path: Path, file_prefix: str) -> List[PpmImagePlugin.PpmImageFile]:
    return pdf2image.convert_from_path(
        pdf_path=pdf_path,
        output_folder=output_path,
        output_file=f"{file_prefix}-")


def parse_images_and_save_text(images: List[PpmImagePlugin.PpmImageFile], output_path: Path, file_prefix: str, lang: str) -> List[TextPage]:
    en_pages: List[TextPage] = []

    for index, image in enumerate(images):
        page = index + 1
        file_name = TEXT_FILE_NAME_TEMPLATE.substitute(
            prefix=file_prefix, lang=lang, page=page)
        file_path = output_path.joinpath(Path(file_name))
        lines = pytesseract.image_to_string(image).split(LINE_ENDING)

        en_page = TextPage(lang=lang,
                           page_number=page,
                           lines=lines,
                           path=file_path)
        en_page.save_to_disk()
        en_pages.append(en_page)
        logging.info(
            f"Parsed {image.filename} to a text file {file_path}.")

    return en_pages


def translate_pages_and_save_text(pages: List[TextPage], output_path: Path, file_prefix: str, src_lang: str, dest_lang: str) -> List[TextPage]:
    credentials, project_id = google.auth.default()
    TRANSLATE_CLIENT = translate.Client()

    trans_pages: List[TextPage] = []

    for page in pages:
        trans_result = TRANSLATE_CLIENT.translate(
            values=page.lines, target_language=dest_lang, source_language=src_lang)
        trans_lines = [result["translatedText"] for result in trans_result]
        file_name = TEXT_FILE_NAME_TEMPLATE.substitute(
            prefix=file_prefix, lang=dest_lang, page=page.page_number)
        file_path = output_path.joinpath(Path(file_name))

        trans_page = TextPage(lang=dest_lang,
                              page_number=page.page_number,
                              lines=trans_lines,
                              path=file_path)
        trans_page.save_to_disk()
        trans_pages.append(trans_page)
        logging.info(
            f"Translated {page.path} ({page.lang}) to {trans_page.path} ({trans_page.lang}).")

    return trans_pages


if __name__ == "__main__":
    load_dotenv()

    PDF_PATH = Path("assets/manuaali.pdf").resolve()
    FILE_PREFIX = PDF_PATH.stem

    # Output directory structure
    OUTPUT_DIR = Path("output/").resolve()
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGE_OUTPUT_DIR = OUTPUT_DIR.joinpath(Path("images/")).resolve()
    IMAGE_OUTPUT_DIR.mkdir(exist_ok=True)
    TEXT_OUTPUT_DIR = OUTPUT_DIR.joinpath(Path("text/")).resolve()
    TEXT_OUTPUT_DIR.mkdir(exist_ok=True)
    logging.info("Created output directories.")

    # PDF to image conversion
    images = convert_pdf_and_save_images(PDF_PATH,
                                         IMAGE_OUTPUT_DIR,
                                         FILE_PREFIX)
    logging.info(f"Converted the PDF to {len(images)} images.")

    # Text parsing
    SRC_LANG = "en"
    en_pages = parse_images_and_save_text(images,
                                          TEXT_OUTPUT_DIR,
                                          FILE_PREFIX,
                                          SRC_LANG)

    # Text translation
    DEST_LANG = "fi"
    fi_pages = translate_pages_and_save_text(en_pages,
                                             TEXT_OUTPUT_DIR,
                                             FILE_PREFIX,
                                             SRC_LANG,
                                             DEST_LANG)
