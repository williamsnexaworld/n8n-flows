"""
Módulo para hacer scraping de contenido público de Facebook e Instagram
"""

import requests
import time
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from loguru import logger
import re
from urllib.parse import urlparse, urljoin
from PIL import Image
import urllib.request
import hashlib
from retry import retry

@dataclass
class Post:
    """Clase para representar un post de redes sociales"""
    plataforma: str  # 'facebook' o 'instagram'
    url_post: str
    texto: str
    hashtags: List[str]
    fecha_publicacion: Optional[str] = None
    tipo_contenido: str = "texto"  # texto, imagen, video, carrusel
    url_imagen: Optional[str] = None
    url_video: Optional[str] = None
    likes: Optional[int] = None
    comentarios: Optional[int] = None
    compartidos: Optional[int] = None
    fuente: str = ""  # nombre del competidor
    timestamp_scraping: str = ""
    
    def __post_init__(self):
        if not self.timestamp_scraping:
            self.timestamp_scraping = datetime.now().isoformat()

class SocialScraper:
    """Clase principal para hacer scraping de redes sociales"""
    
    def __init__(self, headless: bool = True, media_storage_path: str = "./media_storage"):
        self.headless = headless
        self.media_storage_path = media_storage_path
        self.driver = None
        self.session = requests.Session()
        
        # Headers para parecer un navegador real
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Crear directorio para almacenar media
        os.makedirs(media_storage_path, exist_ok=True)
    
    def _crear_driver(self):
        """Crea una instancia del navegador Chrome"""
        if self.driver:
            return self.driver
            
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument('--headless')
            
            # Configuraciones para mejorar compatibilidad
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Configurar User-Agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Driver de Chrome iniciado correctamente")
            return self.driver
            
        except Exception as e:
            logger.error(f"Error al crear driver de Chrome: {e}")
            raise
    
    def cerrar_driver(self):
        """Cierra el navegador"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Driver cerrado correctamente")
            except Exception as e:
                logger.error(f"Error al cerrar driver: {e}")
    
    @retry(tries=3, delay=2)
    def scrape_facebook_page(self, facebook_url: str, max_posts: int = 3) -> List[Post]:
        """Hace scraping de una página pública de Facebook"""
        posts = []
        
        try:
            logger.info(f"Iniciando scraping de Facebook: {facebook_url}")
            
            if not self.driver:
                self._crear_driver()
            
            # Ir a la página
            self.driver.get(facebook_url)
            time.sleep(3)
            
            # Esperar a que cargue la página
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll hacia abajo para cargar más contenido
            self._scroll_page(3)
            
            # Buscar posts
            posts_elements = self._encontrar_posts_facebook()
            
            for i, post_element in enumerate(posts_elements[:max_posts]):
                try:
                    post_data = self._extraer_datos_post_facebook(post_element)
                    if post_data:
                        post = Post(
                            plataforma="facebook",
                            url_post=post_data.get('url', facebook_url),
                            texto=post_data.get('texto', ''),
                            hashtags=self._extraer_hashtags(post_data.get('texto', '')),
                            fecha_publicacion=post_data.get('fecha'),
                            tipo_contenido=post_data.get('tipo', 'texto'),
                            url_imagen=post_data.get('imagen'),
                            url_video=post_data.get('video'),
                            likes=post_data.get('likes'),
                            comentarios=post_data.get('comentarios'),
                            compartidos=post_data.get('compartidos'),
                            fuente=self._extraer_nombre_pagina_facebook()
                        )
                        posts.append(post)
                        
                        # Descargar media si existe
                        if post.url_imagen:
                            self._descargar_media(post.url_imagen, f"fb_img_{i}")
                        
                except Exception as e:
                    logger.warning(f"Error al procesar post {i} de Facebook: {e}")
                    continue
            
            logger.info(f"Scraping completado: {len(posts)} posts extraídos de Facebook")
            
        except Exception as e:
            logger.error(f"Error en scraping de Facebook: {e}")
        
        return posts
    
    @retry(tries=3, delay=2)
    def scrape_instagram_page(self, instagram_url: str, max_posts: int = 3) -> List[Post]:
        """Hace scraping de una página pública de Instagram"""
        posts = []
        
        try:
            logger.info(f"Iniciando scraping de Instagram: {instagram_url}")
            
            if not self.driver:
                self._crear_driver()
            
            # Ir a la página
            self.driver.get(instagram_url)
            time.sleep(3)
            
            # Esperar a que cargue la página
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll hacia abajo para cargar más contenido
            self._scroll_page(2)
            
            # Buscar posts
            posts_elements = self._encontrar_posts_instagram()
            
            for i, post_element in enumerate(posts_elements[:max_posts]):
                try:
                    post_data = self._extraer_datos_post_instagram(post_element)
                    if post_data:
                        post = Post(
                            plataforma="instagram",
                            url_post=post_data.get('url', instagram_url),
                            texto=post_data.get('texto', ''),
                            hashtags=self._extraer_hashtags(post_data.get('texto', '')),
                            fecha_publicacion=post_data.get('fecha'),
                            tipo_contenido=post_data.get('tipo', 'imagen'),
                            url_imagen=post_data.get('imagen'),
                            url_video=post_data.get('video'),
                            likes=post_data.get('likes'),
                            comentarios=post_data.get('comentarios'),
                            fuente=self._extraer_nombre_perfil_instagram()
                        )
                        posts.append(post)
                        
                        # Descargar media si existe
                        if post.url_imagen:
                            self._descargar_media(post.url_imagen, f"ig_img_{i}")
                        
                except Exception as e:
                    logger.warning(f"Error al procesar post {i} de Instagram: {e}")
                    continue
            
            logger.info(f"Scraping completado: {len(posts)} posts extraídos de Instagram")
            
        except Exception as e:
            logger.error(f"Error en scraping de Instagram: {e}")
        
        return posts
    
    def _scroll_page(self, num_scrolls: int = 3):
        """Hace scroll en la página para cargar más contenido"""
        try:
            for i in range(num_scrolls):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Error al hacer scroll: {e}")
    
    def _encontrar_posts_facebook(self) -> List:
        """Encuentra elementos de posts en Facebook"""
        try:
            # Múltiples selectores para diferentes versiones de Facebook
            selectores = [
                '[data-pagelet="FeedUnit"]',
                '[role="article"]',
                '[data-testid="fbfeed_story"]',
                '.userContentWrapper'
            ]
            
            for selector in selectores:
                try:
                    posts = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if posts:
                        logger.info(f"Encontrados {len(posts)} posts con selector: {selector}")
                        return posts[:10]  # Limitar para evitar sobrecarga
                except:
                    continue
            
            logger.warning("No se encontraron posts con ningún selector")
            return []
            
        except Exception as e:
            logger.error(f"Error al buscar posts de Facebook: {e}")
            return []
    
    def _encontrar_posts_instagram(self) -> List:
        """Encuentra elementos de posts en Instagram"""
        try:
            # Buscar posts en el grid principal
            selectores = [
                'article',
                '[role="button"] img',
                '._aagu',
                '._ac7v'
            ]
            
            for selector in selectores:
                try:
                    posts = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if posts:
                        logger.info(f"Encontrados {len(posts)} posts con selector: {selector}")
                        return posts[:10]  # Limitar para evitar sobrecarga
                except:
                    continue
            
            logger.warning("No se encontraron posts con ningún selector")
            return []
            
        except Exception as e:
            logger.error(f"Error al buscar posts de Instagram: {e}")
            return []
    
    def _extraer_datos_post_facebook(self, post_element) -> Dict:
        """Extrae datos de un post de Facebook"""
        try:
            datos = {}
            
            # Extraer texto
            try:
                texto_elements = post_element.find_elements(By.CSS_SELECTOR, '[data-testid="post_message"], .userContent, [data-ad-preview="message"]')
                if texto_elements:
                    datos['texto'] = texto_elements[0].text.strip()
                else:
                    datos['texto'] = ""
            except:
                datos['texto'] = ""
            
            # Extraer imagen
            try:
                img_elements = post_element.find_elements(By.CSS_SELECTOR, 'img[src*="scontent"]')
                if img_elements:
                    datos['imagen'] = img_elements[0].get_attribute('src')
                    datos['tipo'] = 'imagen'
            except:
                pass
            
            # Extraer video
            try:
                video_elements = post_element.find_elements(By.CSS_SELECTOR, 'video')
                if video_elements:
                    datos['video'] = video_elements[0].get_attribute('src')
                    datos['tipo'] = 'video'
            except:
                pass
            
            # Extraer métricas (intentar, pero puede estar limitado)
            try:
                likes_elements = post_element.find_elements(By.CSS_SELECTOR, '[aria-label*="reactions"], [aria-label*="Me gusta"]')
                if likes_elements:
                    likes_text = likes_elements[0].get_attribute('aria-label') or likes_elements[0].text
                    datos['likes'] = self._extraer_numero_metricas(likes_text)
            except:
                pass
            
            return datos
            
        except Exception as e:
            logger.warning(f"Error al extraer datos del post de Facebook: {e}")
            return {}
    
    def _extraer_datos_post_instagram(self, post_element) -> Dict:
        """Extrae datos de un post de Instagram"""
        try:
            datos = {}
            
            # Para Instagram, primero necesitamos hacer click en el post para ver detalles
            try:
                post_element.click()
                time.sleep(2)
                
                # Esperar a que aparezca el modal
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"]'))
                )
                
                # Extraer datos del modal
                modal = self.driver.find_element(By.CSS_SELECTOR, '[role="dialog"]')
                
                # Extraer texto/caption
                try:
                    caption_elements = modal.find_elements(By.CSS_SELECTOR, 'span[dir="auto"]')
                    caption_text = ""
                    for elem in caption_elements:
                        text = elem.text.strip()
                        if len(text) > 10:  # Filtrar textos muy cortos
                            caption_text = text
                            break
                    datos['texto'] = caption_text
                except:
                    datos['texto'] = ""
                
                # Extraer imagen
                try:
                    img_elements = modal.find_elements(By.CSS_SELECTOR, 'img[src*="scontent"]')
                    if img_elements:
                        datos['imagen'] = img_elements[0].get_attribute('src')
                        datos['tipo'] = 'imagen'
                except:
                    pass
                
                # Extraer video
                try:
                    video_elements = modal.find_elements(By.CSS_SELECTOR, 'video')
                    if video_elements:
                        datos['video'] = video_elements[0].get_attribute('src')
                        datos['tipo'] = 'video'
                except:
                    pass
                
                # Cerrar modal
                try:
                    close_button = modal.find_element(By.CSS_SELECTOR, '[aria-label="Cerrar"], [aria-label="Close"]')
                    close_button.click()
                    time.sleep(1)
                except:
                    # Si no encuentra el botón de cerrar, presionar escape
                    self.driver.execute_script("document.body.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));")
                    time.sleep(1)
                
            except Exception as e:
                logger.warning(f"Error al abrir post de Instagram: {e}")
                # Intentar extraer datos básicos sin abrir el modal
                try:
                    img_element = post_element.find_element(By.CSS_SELECTOR, 'img')
                    if img_element:
                        datos['imagen'] = img_element.get_attribute('src')
                        datos['tipo'] = 'imagen'
                        datos['texto'] = img_element.get_attribute('alt') or ""
                except:
                    pass
            
            return datos
            
        except Exception as e:
            logger.warning(f"Error al extraer datos del post de Instagram: {e}")
            return {}
    
    def _extraer_hashtags(self, texto: str) -> List[str]:
        """Extrae hashtags de un texto"""
        if not texto:
            return []
        
        hashtags = re.findall(r'#\w+', texto)
        return [tag.lower() for tag in hashtags]
    
    def _extraer_numero_metricas(self, texto: str) -> Optional[int]:
        """Extrae números de métricas (likes, comentarios, etc.)"""
        try:
            # Buscar números en el texto
            numeros = re.findall(r'\d+', texto.replace(',', '').replace('.', ''))
            if numeros:
                return int(numeros[0])
        except:
            pass
        return None
    
    def _extraer_nombre_pagina_facebook(self) -> str:
        """Extrae el nombre de la página de Facebook"""
        try:
            title_elements = self.driver.find_elements(By.CSS_SELECTOR, 'title, h1')
            if title_elements:
                return title_elements[0].text.strip().split(' - ')[0]
        except:
            pass
        return "Facebook Page"
    
    def _extraer_nombre_perfil_instagram(self) -> str:
        """Extrae el nombre del perfil de Instagram"""
        try:
            title_elements = self.driver.find_elements(By.CSS_SELECTOR, 'title, h1, h2')
            if title_elements:
                return title_elements[0].text.strip().split(' (')[0]
        except:
            pass
        return "Instagram Profile"
    
    def _descargar_media(self, url: str, filename_prefix: str) -> Optional[str]:
        """Descarga archivos multimedia"""
        try:
            if not url:
                return None
            
            # Generar nombre de archivo único
            hash_url = hashlib.md5(url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Determinar extensión
            if 'jpg' in url or 'jpeg' in url:
                extension = '.jpg'
            elif 'png' in url:
                extension = '.png'
            elif 'mp4' in url:
                extension = '.mp4'
            else:
                extension = '.jpg'  # Por defecto
            
            filename = f"{filename_prefix}_{timestamp}_{hash_url}{extension}"
            filepath = os.path.join(self.media_storage_path, filename)
            
            # Descargar archivo
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Media descargada: {filepath}")
            return filepath
            
        except Exception as e:
            logger.warning(f"Error al descargar media {url}: {e}")
            return None
    
    def scrape_multiple_pages(self, urls_facebook: List[str], urls_instagram: List[str], max_posts: int = 3) -> Dict[str, List[Post]]:
        """Hace scraping de múltiples páginas"""
        resultados = {
            'facebook': [],
            'instagram': []
        }
        
        try:
            # Scraping de Facebook
            for url in urls_facebook:
                try:
                    posts = self.scrape_facebook_page(url, max_posts)
                    resultados['facebook'].extend(posts)
                    time.sleep(3)  # Pausa entre páginas
                except Exception as e:
                    logger.error(f"Error al procesar página de Facebook {url}: {e}")
            
            # Scraping de Instagram
            for url in urls_instagram:
                try:
                    posts = self.scrape_instagram_page(url, max_posts)
                    resultados['instagram'].extend(posts)
                    time.sleep(3)  # Pausa entre páginas
                except Exception as e:
                    logger.error(f"Error al procesar página de Instagram {url}: {e}")
            
        finally:
            self.cerrar_driver()
        
        return resultados
    
    def guardar_posts_json(self, posts: List[Post], filepath: str):
        """Guarda los posts en formato JSON"""
        try:
            posts_dict = [asdict(post) for post in posts]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(posts_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Posts guardados en: {filepath}")
            
        except Exception as e:
            logger.error(f"Error al guardar posts en JSON: {e}")
    
    def cargar_posts_json(self, filepath: str) -> List[Post]:
        """Carga posts desde un archivo JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                posts_dict = json.load(f)
            
            posts = []
            for post_data in posts_dict:
                post = Post(**post_data)
                posts.append(post)
            
            logger.info(f"Cargados {len(posts)} posts desde: {filepath}")
            return posts
            
        except Exception as e:
            logger.error(f"Error al cargar posts desde JSON: {e}")
            return []

# Función de utilidad
def scrape_competencia(urls_facebook: List[str], urls_instagram: List[str], max_posts: int = 3, headless: bool = True) -> Dict[str, List[Post]]:
    """Función de conveniencia para hacer scraping de la competencia"""
    scraper = SocialScraper(headless=headless)
    try:
        return scraper.scrape_multiple_pages(urls_facebook, urls_instagram, max_posts)
    finally:
        scraper.cerrar_driver()

if __name__ == "__main__":
    # Ejemplo de uso
    urls_facebook = [
        "https://facebook.com/ejemplo1",
        "https://facebook.com/ejemplo2"
    ]
    
    urls_instagram = [
        "https://instagram.com/ejemplo1",
        "https://instagram.com/ejemplo2"
    ]
    
    resultados = scrape_competencia(urls_facebook, urls_instagram, max_posts=3)
    
    print(f"Posts de Facebook: {len(resultados['facebook'])}")
    print(f"Posts de Instagram: {len(resultados['instagram'])}")
    
    # Guardar resultados
    scraper = SocialScraper()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scraper.guardar_posts_json(
        resultados['facebook'] + resultados['instagram'],
        f"../data/posts_competencia_{timestamp}.json"
    )