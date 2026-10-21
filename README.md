# MCP PDF OCR Server

A Model Context Protocol (MCP) server that enables Large Language Models (LLMs) to perform Optical Character Recognition (OCR) on PDF documents using local Vision models via **LM Studio**.

This tool allows AI assistants to "read" PDFs, preserving original languages, mathematical formulas ($LaTeX$), and document structure, while avoiding external cloud APIs by leveraging your local hardware.

## Features

- **Local & Private**: All processing happens locally via LM Studio.
- **Vision Model Support**: Automatically detects and uses the first available Vision-capable model loaded in LM Studio.
- **Chunked Processing**: Process specific pages or ranges to avoid context limits and client timeouts.
- **High-Fidelity Output**:
  - Preserves original language.
  - Converts mathematical formulas to $LaTeX$.
  - Maintains Markdown structure (headers, lists, tables).
- **Smart Fallback**: Uses `PyMuPDF` for fast conversion, with `pdf2image` as a backup.
- **Debugging**: Saves recognized text to `.txt` files locally for verification.

## Prerequisites

1. **Python 3.9+**
2. **LM Studio**: Running locally with the Server enabled.
   - Ensure you have at least one **Vision-capable model** loaded (e.g., LLaVA, BakLLaVA, Moondream, Yi-VL).
3. **System Dependencies**:
   - For best performance, ensure `poppler-utils` is installed if you plan to use the `pdf2image` fallback (though `PyMuPDF` is preferred and doesn't require it).

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/mcp-pdf-ocr-server.git
   cd mcp-pdf-ocr-server
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install fastmcp pymupdf pillow requests
   ```

## Configuration

### MCP Client Setup

Add the server to your MCP client configuration (LMstudio itself or Claude Desktop, Cursor, etc.).

**Example for Claude Desktop (`claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "pdf-ocr": {
      "command": "python",
      "args": [
        "/absolute/path/to/mcp-pdf-ocr-server/mcp_ocr_server.py"
      ]
    }
  }
}
```

> **Note:** python command should be replaced in case you use venv.

## Usage

Once connected, your AI assistant can use the `ocr_pdf_pages` tool.

### Tool Arguments

| Argument | Type | Description |
| :--- | :--- | :--- |
| `file_path` | `string` | Absolute path to the PDF file. |
| `page_numbers` | `List[int]` | List of page numbers to process (e.g., `[1, 2, 3]`). |
| `dpi` | `int` | Resolution for image conversion (default: `150`). Higher is clearer but slower. |
| `max_chars` | `int` | Optional. Stop processing if total characters exceed this limit. |

### Example Prompts

**1. Read specific pages:**
> "Read pages 1 through 5 of `/home/user/document.pdf` and summarize the key points."

**2. Process a large document in chunks:**
> "Start reading `/home/user/book.pdf`. Process pages 1-10 first, then continue with 11-20."

**3. Extract formulas:**
> "Extract all mathematical formulas from page 42 of `/home/user/physics.pdf` in LaTeX format."

## How It Works

1. **Model Selection**: The server queries LM Studio's API (`/v1/models`) and selects the first available model.
2. **Vision Check**: It sends a tiny test image to verify the model supports vision capabilities.
3. **PDF Conversion**: Uses `PyMuPDF` to convert specified PDF pages into high-quality images.
4. **OCR Inference**: Sends each image to LM Studio with a strict prompt enforcing:
   - No internal "thinking" output.
   - LaTeX for math.
   - Original language preservation.
5. **Aggregation**: Combines results and saves them to a `.txt` file in the script's directory for debugging.

## Troubleshooting

- **"Plugin process exited unexpectedly"**:
  - Ensure all `print()` statements are removed or redirected to `stderr`. This version uses `logging` to `stderr` to prevent breaking the MCP JSON protocol.
  - Check that `fastmcp` is installed in the correct Python environment.

- **"Request timed out"**:
  - OCR is computationally expensive. If processing many pages, reduce the `page_numbers` list size (e.g., 5–10 pages per call).
  - Lower the `dpi` to `100` or `150` for faster processing.

- **"No vision-capable model found"**:
  - Ensure you have loaded a Vision model in LM Studio (not just a text-only LLM).
  - Check LM Studio logs to ensure the server is running on port `1234`.

## P.S.

Developed for LM Studio usage with its API and this is the best way to use it. LM Studio can process all data with only one model loaded.

## License

MIT License
