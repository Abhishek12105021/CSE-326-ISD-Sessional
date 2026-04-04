# CSE-326: Information System Design Sessional

This repository contains all deliverables for the **CSE-326 ISD Lab** course — six individual presentations covering core system design topics, followed by a group project building a full-stack YouTube Clone.

## Team — Group 6

| Member | Presentation Topic |
|--------|--------------------|
| Nawriz Ahmed Turjo | BPMN |
| Abhishek Roy | Use Case & Class Diagram |
| Shams Hossain Shimanto | Collaboration Diagram |
| Monjur Hossain Khan Shovon | Mock UI |
| Amit Saha | State & Sequence Diagram |
| Abrar Jahin | API Documentation |

## Project — YouTube Clone

A full-stack YouTube clone with an **AI-powered recommendation engine**, semantic search, and a modern React UI. The complete source code, setup instructions, and detailed documentation are in the [`Youtube/`](Youtube/) directory.

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, Supabase Auth |
| Backend | FastAPI, Python 3.11+ |
| Database | Supabase (PostgreSQL + pgvector) |
| ML/Search | FAISS, Sentence Transformers (BAAI/bge-m3) |
| CI/CD | GitHub Actions, Vercel, Modal/Render |

See [`Youtube/README.md`](Youtube/README.md) for full project details, setup guide, and architecture.

## Report

The final project report is available as a compiled PDF.

- [`Report/G3-Youtube.pdf`](Report/G3-Youtube.pdf)

## Repository Structure

```
ISD Lab/
├── API/                    # API documentation (OpenAPI spec)
├── BPMN/                   # BPMN diagrams
├── Collaboration/          # Collaboration diagram
├── Mock UI/                # UI mockup
├── Report/                 # Final report (LaTeX + PDF)
├── Sequence + State/       # Sequence & State diagrams
├── UseCase + Class/        # Use Case & Class diagrams
├── Youtube/                # Full-stack YouTube clone (see its own README)
└── .github/workflows/      # CI/CD pipelines
```
