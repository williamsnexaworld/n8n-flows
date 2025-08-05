"""
Módulo para publicar contenido automáticamente en Facebook e Instagram
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger
import facebook
from instagrapi import Client as InstagramClient
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired
import tempfile
from PIL import Image
import io
from pathlib import Path

@dataclass
class PublicacionResult:
    """Resultado de una publicación"""
    exito: bool
    plataforma: str
    post_id: Optional[str] = None
    url_publicacion: Optional[str] = None
    mensaje_error: Optional[str] = None
    fecha_publicacion: str = ""
    texto_publicado: str = ""
    hashtags_usados: List[str] = None
    engagement_inicial: Dict[str, int] = None
    
    def __post_init__(self):
        if not self.fecha_publicacion:
            self.fecha_publicacion = datetime.now().isoformat()
        if self.hashtags_usados is None:
            self.hashtags_usados = []
        if self.engagement_inicial is None:
            self.engagement_inicial = {}

class SocialPublisher:
    """Publicador automático para redes sociales"""
    
    def __init__(self, facebook_config: Dict = None, instagram_config: Dict = None):
        """
        Inicializa el publicador
        
        Args:
            facebook_config: Configuración de Facebook API
            instagram_config: Configuración de Instagram
        """
        self.facebook_config = facebook_config or {}
        self.instagram_config = instagram_config or {}
        
        # Clientes de API
        self.facebook_api = None
        self.instagram_client = None
        
        # Configuraciones
        self.max_retries = 3
        self.retry_delay = 5  # segundos
        
        # Inicializar APIs
        self._inicializar_facebook()
        self._inicializar_instagram()
    
    def _inicializar_facebook(self):
        """Inicializa la API de Facebook"""
        try:
            if not self.facebook_config:
                logger.warning("Configuración de Facebook no proporcionada")
                return
            
            required_keys = ['access_token', 'page_id']
            if not all(key in self.facebook_config for key in required_keys):
                logger.warning("Faltan credenciales requeridas para Facebook")
                return
            
            # Inicializar API de Facebook
            self.facebook_api = facebook.GraphAPI(
                access_token=self.facebook_config['access_token'],
                version='18.0'
            )
            
            # Verificar credenciales
            try:
                page_info = self.facebook_api.get_object(
                    id=self.facebook_config['page_id'],
                    fields='name,id'
                )
                logger.info(f"Facebook API inicializada para página: {page_info.get('name', 'Desconocida')}")
                
            except Exception as e:
                logger.error(f"Error al verificar credenciales de Facebook: {e}")
                self.facebook_api = None
                
        except Exception as e:
            logger.error(f"Error al inicializar Facebook API: {e}")
            self.facebook_api = None
    
    def _inicializar_instagram(self):
        """Inicializa el cliente de Instagram"""
        try:
            if not self.instagram_config:
                logger.warning("Configuración de Instagram no proporcionada")
                return
            
            required_keys = ['username', 'password']
            if not all(key in self.instagram_config for key in required_keys):
                logger.warning("Faltan credenciales requeridas para Instagram")
                return
            
            # Inicializar cliente de Instagram
            self.instagram_client = InstagramClient()
            
            # Configurar settings de sesión
            session_file = f"./data/instagram_session_{self.instagram_config['username']}.json"
            if os.path.exists(session_file):
                self.instagram_client.load_settings(session_file)
            
            # Intentar login
            try:
                self.instagram_client.login(
                    username=self.instagram_config['username'],
                    password=self.instagram_config['password']
                )
                
                # Guardar sesión
                self.instagram_client.dump_settings(session_file)
                
                logger.info(f"Instagram cliente inicializado para usuario: {self.instagram_config['username']}")
                
            except (LoginRequired, ChallengeRequired, TwoFactorRequired) as e:
                logger.error(f"Error de autenticación en Instagram: {e}")
                self.instagram_client = None
                
        except Exception as e:
            logger.error(f"Error al inicializar Instagram cliente: {e}")
            self.instagram_client = None
    
    def publicar_facebook(self, texto: str, imagen_path: Optional[str] = None, hashtags: List[str] = None) -> PublicacionResult:
        """Publica contenido en Facebook"""
        try:
            logger.info("Iniciando publicación en Facebook...")
            
            if not self.facebook_api:
                return PublicacionResult(
                    exito=False,
                    plataforma="facebook",
                    mensaje_error="API de Facebook no inicializada"
                )
            
            # Preparar texto completo
            texto_completo = texto
            if hashtags:
                hashtags_texto = " ".join(hashtags)
                texto_completo = f"{texto}\n\n{hashtags_texto}"
            
            # Publicar según el tipo de contenido
            post_data = {'message': texto_completo}
            
            if imagen_path and os.path.exists(imagen_path):
                # Publicación con imagen
                with open(imagen_path, 'rb') as image_file:
                    result = self.facebook_api.put_photo(
                        image=image_file,
                        message=texto_completo,
                        album_path=f"{self.facebook_config['page_id']}/photos"
                    )
            else:
                # Publicación solo texto
                result = self.facebook_api.put_object(
                    parent_object=self.facebook_config['page_id'],
                    connection_name='feed',
                    **post_data
                )
            
            post_id = result.get('id') if result else None
            url_publicacion = f"https://facebook.com/{post_id}" if post_id else None
            
            logger.info(f"Publicación exitosa en Facebook: {post_id}")
            
            return PublicacionResult(
                exito=True,
                plataforma="facebook",
                post_id=post_id,
                url_publicacion=url_publicacion,
                texto_publicado=texto_completo,
                hashtags_usados=hashtags or []
            )
            
        except Exception as e:
            logger.error(f"Error al publicar en Facebook: {e}")
            return PublicacionResult(
                exito=False,
                plataforma="facebook",
                mensaje_error=str(e),
                texto_publicado=texto,
                hashtags_usados=hashtags or []
            )
    
    def publicar_instagram(self, texto: str, imagen_path: Optional[str] = None, hashtags: List[str] = None) -> PublicacionResult:
        """Publica contenido en Instagram"""
        try:
            logger.info("Iniciando publicación en Instagram...")
            
            if not self.instagram_client:
                return PublicacionResult(
                    exito=False,
                    plataforma="instagram",
                    mensaje_error="Cliente de Instagram no inicializado"
                )
            
            # Preparar texto completo
            texto_completo = texto
            if hashtags:
                hashtags_texto = " ".join(hashtags)
                texto_completo = f"{texto}\n\n{hashtags_texto}"
            
            # Instagram requiere imagen para posts normales
            if not imagen_path or not os.path.exists(imagen_path):
                # Crear imagen simple con texto si no se proporciona
                imagen_path = self._crear_imagen_texto(texto)
            
            # Redimensionar imagen si es necesario
            imagen_procesada = self._procesar_imagen_instagram(imagen_path)
            
            # Publicar
            if imagen_procesada:
                media = self.instagram_client.photo_upload(
                    path=imagen_procesada,
                    caption=texto_completo
                )
                
                post_id = media.id if media else None
                url_publicacion = f"https://instagram.com/p/{media.code}/" if media else None
                
                # Limpiar archivo temporal si se creó
                if imagen_procesada != imagen_path and os.path.exists(imagen_procesada):
                    os.remove(imagen_procesada)
                
                logger.info(f"Publicación exitosa en Instagram: {post_id}")
                
                return PublicacionResult(
                    exito=True,
                    plataforma="instagram",
                    post_id=post_id,
                    url_publicacion=url_publicacion,
                    texto_publicado=texto_completo,
                    hashtags_usados=hashtags or []
                )
            else:
                raise Exception("No se pudo procesar la imagen para Instagram")
                
        except Exception as e:
            logger.error(f"Error al publicar en Instagram: {e}")
            return PublicacionResult(
                exito=False,
                plataforma="instagram",
                mensaje_error=str(e),
                texto_publicado=texto,
                hashtags_usados=hashtags or []
            )
    
    def publicar_historia_instagram(self, imagen_path: str, texto: Optional[str] = None) -> PublicacionResult:
        """Publica una historia en Instagram"""
        try:
            logger.info("Publicando historia en Instagram...")
            
            if not self.instagram_client:
                return PublicacionResult(
                    exito=False,
                    plataforma="instagram_story",
                    mensaje_error="Cliente de Instagram no inicializado"
                )
            
            if not imagen_path or not os.path.exists(imagen_path):
                raise Exception("Se requiere imagen para historia de Instagram")
            
            # Procesar imagen para historia (formato 9:16)
            imagen_procesada = self._procesar_imagen_historia(imagen_path)
            
            # Publicar historia
            story = self.instagram_client.photo_upload_to_story(
                path=imagen_procesada
            )
            
            # Limpiar archivo temporal
            if imagen_procesada != imagen_path and os.path.exists(imagen_procesada):
                os.remove(imagen_procesada)
            
            post_id = story.id if story else None
            
            logger.info(f"Historia publicada exitosamente: {post_id}")
            
            return PublicacionResult(
                exito=True,
                plataforma="instagram_story",
                post_id=post_id,
                texto_publicado=texto or "",
            )
            
        except Exception as e:
            logger.error(f"Error al publicar historia en Instagram: {e}")
            return PublicacionResult(
                exito=False,
                plataforma="instagram_story",
                mensaje_error=str(e)
            )
    
    def _crear_imagen_texto(self, texto: str) -> str:
        """Crea una imagen simple con texto"""
        try:
            # Usar el generador de imágenes del content_generator
            from content_generator import ContentGenerator
            
            # Crear directorio temporal
            temp_dir = "./temp_images"
            os.makedirs(temp_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{temp_dir}/texto_imagen_{timestamp}.png"
            
            # Crear imagen básica con PIL
            from PIL import Image, ImageDraw, ImageFont
            
            width, height = 1080, 1080
            img = Image.new('RGB', (width, height), color='#4A90E2')
            draw = ImageDraw.Draw(img)
            
            # Configurar fuente
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            # Dividir texto en líneas
            from textwrap import wrap
            lines = wrap(texto[:200], 30)  # Limitar texto
            
            # Calcular posición
            total_height = len(lines) * 50
            start_y = (height - total_height) // 2
            
            # Dibujar texto
            for i, line in enumerate(lines):
                text_width = draw.textlength(line, font=font)
                x = (width - text_width) // 2
                y = start_y + i * 50
                draw.text((x, y), line, fill='white', font=font)
            
            img.save(output_path, "PNG")
            return output_path
            
        except Exception as e:
            logger.error(f"Error al crear imagen de texto: {e}")
            return None
    
    def _procesar_imagen_instagram(self, imagen_path: str) -> Optional[str]:
        """Procesa imagen para Instagram (formato cuadrado)"""
        try:
            with Image.open(imagen_path) as img:
                # Convertir a RGB si es necesario
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Redimensionar a formato cuadrado (1080x1080)
                size = (1080, 1080)
                
                # Crear imagen cuadrada con padding si es necesario
                img_ratio = img.width / img.height
                
                if img_ratio > 1:  # Imagen más ancha
                    new_width = int(size[1] * img_ratio)
                    img = img.resize((new_width, size[1]))
                    left = (new_width - size[0]) // 2
                    img = img.crop((left, 0, left + size[0], size[1]))
                elif img_ratio < 1:  # Imagen más alta
                    new_height = int(size[0] / img_ratio)
                    img = img.resize((size[0], new_height))
                    top = (new_height - size[1]) // 2
                    img = img.crop((0, top, size[0], top + size[1]))
                else:  # Imagen ya cuadrada
                    img = img.resize(size)
                
                # Guardar imagen procesada
                temp_path = f"{imagen_path}_processed.jpg"
                img.save(temp_path, "JPEG", quality=95)
                
                return temp_path
                
        except Exception as e:
            logger.error(f"Error al procesar imagen: {e}")
            return None
    
    def _procesar_imagen_historia(self, imagen_path: str) -> Optional[str]:
        """Procesa imagen para historia de Instagram (formato 9:16)"""
        try:
            with Image.open(imagen_path) as img:
                # Convertir a RGB si es necesario
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Redimensionar a formato de historia (1080x1920)
                size = (1080, 1920)
                
                # Crear imagen con ratio 9:16
                img_ratio = img.width / img.height
                target_ratio = size[0] / size[1]
                
                if img_ratio > target_ratio:  # Imagen más ancha
                    new_width = int(size[1] * img_ratio)
                    img = img.resize((new_width, size[1]))
                    left = (new_width - size[0]) // 2
                    img = img.crop((left, 0, left + size[0], size[1]))
                else:  # Imagen más alta o igual
                    new_height = int(size[0] / img_ratio)
                    img = img.resize((size[0], new_height))
                    top = (new_height - size[1]) // 2
                    img = img.crop((0, top, size[0], top + size[1]))
                
                # Guardar imagen procesada
                temp_path = f"{imagen_path}_story.jpg"
                img.save(temp_path, "JPEG", quality=95)
                
                return temp_path
                
        except Exception as e:
            logger.error(f"Error al procesar imagen para historia: {e}")
            return None
    
    def publicar_contenido_generado(self, contenido_generado, imagen_path: Optional[str] = None) -> PublicacionResult:
        """Publica contenido generado por el ContentGenerator"""
        try:
            if contenido_generado.plataforma == "facebook":
                return self.publicar_facebook(
                    texto=contenido_generado.texto,
                    imagen_path=imagen_path or contenido_generado.imagen_local,
                    hashtags=contenido_generado.hashtags
                )
            elif contenido_generado.plataforma == "instagram":
                return self.publicar_instagram(
                    texto=contenido_generado.texto,
                    imagen_path=imagen_path or contenido_generado.imagen_local,
                    hashtags=contenido_generado.hashtags
                )
            else:
                raise ValueError(f"Plataforma no soportada: {contenido_generado.plataforma}")
                
        except Exception as e:
            logger.error(f"Error al publicar contenido generado: {e}")
            return PublicacionResult(
                exito=False,
                plataforma=contenido_generado.plataforma,
                mensaje_error=str(e)
            )
    
    def publicar_multiples_contenidos(self, contenidos_generados: List, imagenes_paths: List[Optional[str]] = None) -> List[PublicacionResult]:
        """Publica múltiples contenidos con delays entre publicaciones"""
        resultados = []
        imagenes_paths = imagenes_paths or [None] * len(contenidos_generados)
        
        for i, contenido in enumerate(contenidos_generados):
            try:
                logger.info(f"Publicando contenido {i+1}/{len(contenidos_generados)}")
                
                imagen_path = imagenes_paths[i] if i < len(imagenes_paths) else None
                resultado = self.publicar_contenido_generado(contenido, imagen_path)
                resultados.append(resultado)
                
                # Delay entre publicaciones para evitar rate limiting
                if i < len(contenidos_generados) - 1:
                    delay = 30  # 30 segundos entre publicaciones
                    logger.info(f"Esperando {delay} segundos antes de la siguiente publicación...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error al publicar contenido {i+1}: {e}")
                resultado = PublicacionResult(
                    exito=False,
                    plataforma=getattr(contenido, 'plataforma', 'desconocida'),
                    mensaje_error=str(e)
                )
                resultados.append(resultado)
        
        return resultados
    
    def obtener_metricas_post(self, post_id: str, plataforma: str) -> Dict:
        """Obtiene métricas básicas de un post"""
        try:
            if plataforma == "facebook" and self.facebook_api:
                try:
                    metrics = self.facebook_api.get_object(
                        id=post_id,
                        fields='likes.summary(true),comments.summary(true),shares'
                    )
                    
                    return {
                        'likes': metrics.get('likes', {}).get('summary', {}).get('total_count', 0),
                        'comments': metrics.get('comments', {}).get('summary', {}).get('total_count', 0),
                        'shares': metrics.get('shares', {}).get('count', 0)
                    }
                except:
                    pass
            
            elif plataforma == "instagram" and self.instagram_client:
                try:
                    media_info = self.instagram_client.media_info(int(post_id))
                    return {
                        'likes': media_info.like_count,
                        'comments': media_info.comment_count,
                        'views': getattr(media_info, 'view_count', 0)
                    }
                except:
                    pass
            
            return {}
            
        except Exception as e:
            logger.warning(f"Error al obtener métricas: {e}")
            return {}
    
    def verificar_estado_apis(self) -> Dict[str, bool]:
        """Verifica el estado de las APIs"""
        estado = {
            'facebook': False,
            'instagram': False
        }
        
        # Verificar Facebook
        if self.facebook_api:
            try:
                self.facebook_api.get_object('me')
                estado['facebook'] = True
            except:
                pass
        
        # Verificar Instagram
        if self.instagram_client:
            try:
                self.instagram_client.account_info()
                estado['instagram'] = True
            except:
                pass
        
        return estado
    
    def guardar_resultados_publicacion(self, resultados: List[PublicacionResult], filepath: str):
        """Guarda resultados de publicaciones en archivo JSON"""
        try:
            resultados_dict = [asdict(resultado) for resultado in resultados]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(resultados_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Resultados guardados en: {filepath}")
            
        except Exception as e:
            logger.error(f"Error al guardar resultados: {e}")
    
    def cargar_resultados_publicacion(self, filepath: str) -> List[PublicacionResult]:
        """Carga resultados desde archivo JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                resultados_dict = json.load(f)
            
            resultados = []
            for resultado_data in resultados_dict:
                resultado = PublicacionResult(**resultado_data)
                resultados.append(resultado)
            
            logger.info(f"Cargados {len(resultados)} resultados desde: {filepath}")
            return resultados
            
        except Exception as e:
            logger.error(f"Error al cargar resultados: {e}")
            return []

# Funciones de utilidad
def crear_publisher_desde_config(config: Dict) -> SocialPublisher:
    """Crea un publisher desde configuración"""
    facebook_config = config.get('facebook', {})
    instagram_config = config.get('instagram', {})
    
    return SocialPublisher(facebook_config, instagram_config)

def publicar_campana_completa(contenidos_generados: List, config: Dict) -> List[PublicacionResult]:
    """Función de conveniencia para publicar una campaña completa"""
    publisher = crear_publisher_desde_config(config)
    return publisher.publicar_multiples_contenidos(contenidos_generados)

if __name__ == "__main__":
    # Ejemplo de uso
    from content_generator import GeneratedContent
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Configuración de ejemplo
    config = {
        'facebook': {
            'access_token': os.getenv('FACEBOOK_ACCESS_TOKEN', ''),
            'page_id': os.getenv('FACEBOOK_PAGE_ID', '')
        },
        'instagram': {
            'username': os.getenv('INSTAGRAM_USERNAME', ''),
            'password': os.getenv('INSTAGRAM_PASSWORD', '')
        }
    }
    
    # Crear publisher
    publisher = SocialPublisher(config['facebook'], config['instagram'])
    
    # Verificar estado
    estado = publisher.verificar_estado_apis()
    print(f"Estado de APIs: {estado}")
    
    # Ejemplo de contenido
    contenido_ejemplo = GeneratedContent(
        texto="¡Probando nuestro agente de marketing automático! 🚀",
        hashtags=["#automation", "#marketing", "#ai"],
        plataforma="instagram",
        tipo_contenido="texto"
    )
    
    # Publicar (solo si las APIs están configuradas)
    if any(estado.values()):
        resultado = publisher.publicar_contenido_generado(contenido_ejemplo)
        print(f"Resultado de publicación: {resultado}")
    else:
        print("APIs no configuradas - no se puede publicar")