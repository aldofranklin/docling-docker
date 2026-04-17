import hashlib
import json
import logging
import os
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, module="torch.utils.data.dataloader")

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    ExcelFormatOption,
    ImageFormatOption,
    PdfFormatOption,
    PowerpointFormatOption,
    WordFormatOption,
)


INPUT_DIR = Path(os.getenv("INPUT_DIR", "/data/input"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/data/output"))
RECURSIVE = os.getenv("RECURSIVE", "true").lower() == "true"
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))
STATE_FILE = OUTPUT_DIR / ".processed_files.json"

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("docling-worker")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_fingerprint(path: Path) -> str:
    """
    Assinatura do arquivo baseada em conteúdo + metadados.
    Permite reprocessar apenas arquivos novos ou efetivamente alterados.
    """
    sha = hashlib.sha256()
    sha.update(path.as_posix().encode("utf-8"))
    stat = path.stat()
    sha.update(str(stat.st_size).encode("utf-8"))
    sha.update(str(int(stat.st_mtime_ns)).encode("utf-8"))

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)

    return sha.hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Falha ao ler estado anterior; recriando arquivo de controle.")
    return {}


def save_state(state: dict) -> None:
    ensure_dir(OUTPUT_DIR)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def relative_stem(file_path: Path) -> str:
    """
    Gera nome de saída estável preservando estrutura relativa do input,
    evitando colisão entre arquivos homônimos em subpastas diferentes.
    """
    try:
        rel = file_path.relative_to(INPUT_DIR)
    except ValueError:
        rel = file_path.name
    rel_no_suffix = Path(rel).with_suffix("")
    return str(rel_no_suffix).replace("\\", "__").replace("/", "__")


def save_all_formats(conv_result, output_root: Path):
    doc_name = relative_stem(Path(str(conv_result.input.file)))

    json_dir = ensure_dir(output_root / "json")
    (json_dir / f"{doc_name}.json").write_text(
        json.dumps(conv_result.document.export_to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )

    md_dir = ensure_dir(output_root / "markdown")
    (md_dir / f"{doc_name}.md").write_text(
        conv_result.document.export_to_markdown(),
        encoding="utf-8",
    )

    txt_dir = ensure_dir(output_root / "txt")
    (txt_dir / f"{doc_name}.txt").write_text(
        conv_result.document.export_to_text(),
        encoding="utf-8",
    )

    tag_dir = ensure_dir(output_root / "doctags")
    (tag_dir / f"{doc_name}.doctags").write_text(
        conv_result.document.export_to_doctags(),
        encoding="utf-8",
    )

    csv_dir = ensure_dir(output_root / "csv")
    for idx, table in enumerate(conv_result.document.tables, start=1):
        try:
            df = table.export_to_dataframe()
            csv_path = csv_dir / f"{doc_name}_Tabela{idx}.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8")
        except Exception as exc:
            log.warning("Não foi possível exportar tabela %s de %s: %s", idx, doc_name, exc)


pipeline_options = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
pipeline_options.table_structure_options.do_cell_matching = True

doc_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=PyPdfiumDocumentBackend,
        ),
        InputFormat.DOCX: WordFormatOption(),
        InputFormat.PPTX: PowerpointFormatOption(),
        InputFormat.XLSX: ExcelFormatOption(),
        InputFormat.IMAGE: ImageFormatOption(),
    }
)


def iter_input_files():
    if RECURSIVE:
        files = [p for p in INPUT_DIR.rglob("*") if p.is_file()]
    else:
        files = [p for p in INPUT_DIR.glob("*") if p.is_file()]

    return sorted([p for p in files if p.suffix.lower() in SUPPORTED_EXTENSIONS])


def cleanup_deleted_files(state: dict) -> dict:
    """
    Remove do controle arquivos que já não existem mais na entrada.
    Não apaga outputs antigos; apenas limpa o índice interno.
    """
    existing = set()
    for file_path in iter_input_files():
        existing.add(str(file_path))

    stale_keys = [k for k in state.keys() if k not in existing]
    if stale_keys:
        for k in stale_keys:
            state.pop(k, None)
        save_state(state)
        log.info("Removidos %d registros de arquivos excluídos do controle.", len(stale_keys))

    return state


def process_file(file_path: Path, state: dict) -> None:
    fp = file_fingerprint(file_path)
    old_fp = state.get(str(file_path))

    if old_fp == fp:
        return

    action = "Novo arquivo" if old_fp is None else "Arquivo alterado"
    log.info("%s detectado: %s", action, file_path)

    start = time.time()
    try:
        result = doc_converter.convert(file_path)
        save_all_formats(result, OUTPUT_DIR)
        state[str(file_path)] = fp
        save_state(state)
        elapsed = time.time() - start
        log.info("Concluído: %s em %.2f s", file_path.name, elapsed)
    except Exception as exc:
        log.exception("Falha ao processar %s: %s", file_path.name, exc)


def main():
    ensure_dir(INPUT_DIR)
    ensure_dir(OUTPUT_DIR)
    state = load_state()

    log.info("Monitorando entrada em: %s", INPUT_DIR)
    log.info("Salvando saídas em: %s", OUTPUT_DIR)
    log.info("Intervalo de varredura: %s segundos", SCAN_INTERVAL_SECONDS)
    log.info("Extensões suportadas: %s", ", ".join(sorted(SUPPORTED_EXTENSIONS)))

    while True:
        try:
            state = cleanup_deleted_files(state)
            files = iter_input_files()

            if files:
                for file_path in files:
                    process_file(file_path, state)
            else:
                log.info("Nenhum arquivo suportado encontrado no diretório de entrada.")
        except Exception as exc:
            log.exception("Erro no ciclo de monitoramento: %s", exc)

        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
