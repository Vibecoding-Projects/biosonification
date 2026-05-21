# Структура Проекта

Документ отражает текущее состояние репозитория после удаления старого кода. Основной рабочий контур один: structured `v2`.

## Корень

| Путь | Назначение |
|---|---|
| `README.md` | Обзор, быстрый старт, ссылки на актуальные документы |
| `RUN_FROM_SCRATCH.md` | Полный запуск проекта с нуля |
| `DATASETS_GUIDE.md` | Подключение FASTA и MIDI данных для structured `v2` |
| `requirements.txt` | Зависимости проекта |
| `train_bio_music_v2.py` | CLI обучения structured-пайплайна |
| `generate_from_fasta_v2.py` | CLI генерации MIDI из FASTA |

## Конфигурация

| Путь | Назначение |
|---|---|
| `configs/pipeline_v2_small.json` | Основной конфиг для локального обучения и инференса |

## Пакет `bio_music_pipeline`

| Путь | Назначение |
|---|---|
| `bio_music_pipeline/__init__.py` | Метаданные пакета |
| `bio_music_pipeline/v2/__init__.py` | Stable exports structured `v2` |
| `bio_music_pipeline/v2/bio.py` | Biological sequence encoder |
| `bio_music_pipeline/v2/config.py` | Dataclass-конфиги и загрузка JSON |
| `bio_music_pipeline/v2/corpus.py` | Поиск score-файлов и bootstrap fallback-корпуса `music21` |
| `bio_music_pipeline/v2/structured_music.py` | Извлечение harmony/melody, токенизация и MIDI render |
| `bio_music_pipeline/v2/structured_pairing.py` | Pairing bio fragments с музыкальными сегментами |
| `bio_music_pipeline/v2/structured_model.py` | Bio-conditioned autoregressive Transformer |
| `bio_music_pipeline/v2/structured_train.py` | Обучение harmony и melody моделей |
| `bio_music_pipeline/v2/structured_generate.py` | Inference `FASTA -> MIDI` |
| `bio_music_pipeline/v2/evaluate.py` | Метрики качества generated MIDI и baseline |
| `bio_music_pipeline/v2/dataset_report.py` | Manifest и sanity report по данным |

## CLI Tools

| Путь | Назначение |
|---|---|
| `tools/evaluate_structured_v2.py` | Evaluation-run для checkpoint и FASTA |
| `tools/report_structured_dataset.py` | Отчёт по фактически используемым данным |

## Данные

| Путь | Назначение |
|---|---|
| `data/fasta/quick_sample.fa` | Demo FASTA для smoke-run |
| `data/fasta/README.txt` | Краткая инструкция по FASTA |
| `data/midi/polyphonic_music21/` | Небольшой fallback MIDI-корпус для локальной проверки |
| `data/midi/README.txt` | Краткая инструкция по MIDI |

## Документация

| Путь | Назначение |
|---|---|
| `docs/architecture_and_science.md` | Архитектура и методология |
| `docs/code_walkthrough.md` | Разбор актуальных модулей |
| `docs/project_structure.md` | Эта карта файлов |

## Тесты

| Путь | Назначение |
|---|---|
| `tests/test_v2_pipeline.py` | Smoke-тесты structured `v2`, CLI, evaluation и dataset report |

## Web

| Путь | Назначение |
|---|---|
| `web/app.py` | Flask entrypoint |
| `web/generator.py` | Wrapper вокруг `generate_structured_music_from_fasta()` |
| `web/midi_to_audio.py` | Опциональная MIDI -> OGG/WAV конвертация |
| `web/templates/` | HTML-шаблоны |
| `web/static/` | CSS и JS |
| `web/README.md` | Запуск web-интерфейса |

## Runtime Артефакты

Эти каталоги создаются локально и игнорируются git:

- `results/`
- `outputs/`
- `tmp/`
- `web/output/`

Для воспроизводимости сохраняйте конфиг запуска, `dataset_report.*`, `metrics.json`, metadata генерации и checkpoint. Сами runtime-файлы не считаются частью исходного кода.
