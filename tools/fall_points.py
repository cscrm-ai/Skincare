"""Tool de deteccao de pontos X,Y em imagens via FAL AI (Moondream3).

Utilizada pelo agente Dra. Sync para localizar achados clinicos
em fotografias de pele.
"""

import base64
from pathlib import Path

import fal_client
from agno.tools import tool


def _image_to_data_uri(path: str) -> str:
    """Converte um arquivo local de imagem para data URI (base64)."""
    p = Path(path)
    ext = p.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime = mime_map.get(ext, "image/jpeg")
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:{mime};base64,{b64}"


@tool
def detect_skin_points(image_path: str, query: str) -> str:
    """Detecta as coordenadas X,Y de um achado clinico em uma imagem de pele.

    Use esta ferramenta SEMPRE que precisar marcar a localizacao exata de um
    achado clinico na imagem. Ela envia a imagem para o modelo Moondream3
    via FAL AI e retorna as coordenadas normalizadas (0 a 1) do ponto
    detectado.

    Args:
        image_path: Caminho absoluto para a imagem de pele a ser analisada.
        query: Descricao do elemento a localizar na imagem
               (ex: "mancha pigmentar na bochecha esquerda", "acne na zona T").

    Returns:
        String JSON com as coordenadas {"x": float, "y": float} do achado,
        ou {"x": 0, "y": 0} se nenhum ponto for detectado.
    """
    if image_path.startswith(("http://", "https://")):
        image_url = image_path
    else:
        p = Path(image_path)
        if not p.exists():
            return f'{{"error": "Arquivo nao encontrado: {image_path}"}}'
        image_url = _image_to_data_uri(image_path)

    print(f"[MOONDREAM3] Chamando FAL AI com query: '{query}'")

    result = fal_client.subscribe(
        "fal-ai/moondream3-preview/point",
        arguments={
            "image_url": image_url,
            "prompt": query,
        },
    )

    points = result.get("points", [])

    if points:
        pt = points[0]
        print(f"[MOONDREAM3] Ponto detectado: x={pt['x']}, y={pt['y']}")
        return f'{{"x": {pt["x"]}, "y": {pt["y"]}}}'

    print("[MOONDREAM3] Nenhum ponto detectado")
    return '{"x": 0, "y": 0}'
