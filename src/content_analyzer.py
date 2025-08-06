"""
Módulo para analizar contenido de la competencia y extraer insights para mejorar el contenido propio
"""

import re
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from loguru import logger
import pandas as pd
from textblob import TextBlob
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
import emoji
import cv2
import numpy as np
from PIL import Image, ImageStat
import requests
from io import BytesIO

# Descargar recursos de NLTK si no están disponibles
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

@dataclass
class ContentInsight:
    """Clase para representar insights del contenido"""
    hashtags_mas_usados: List[Tuple[str, int]]
    palabras_clave: List[Tuple[str, int]]
    emojis_mas_usados: List[Tuple[str, int]]
    tipos_contenido: Dict[str, int]
    horarios_publicacion: Dict[str, int]
    longitud_promedio_texto: float
    sentimiento_promedio: float
    colores_dominantes: List[str]
    temas_principales: List[str]
    patrones_engagement: Dict[str, float]
    timestamp_analisis: str = ""
    
    def __post_init__(self):
        if not self.timestamp_analisis:
            self.timestamp_analisis = datetime.now().isoformat()

@dataclass
class CompetitorAnalysis:
    """Análisis completo de un competidor"""
    nombre_competidor: str
    total_posts: int
    plataformas: List[str]
    insights: ContentInsight
    posts_destacados: List[Dict]  # Posts con mayor engagement
    recomendaciones: List[str]

class ContentAnalyzer:
    """Analizador de contenido de redes sociales"""
    
    def __init__(self, idioma: str = "spanish"):
        self.idioma = idioma
        self.stemmer = SnowballStemmer(idioma)
        
        # Cargar stopwords
        try:
            self.stopwords = set(stopwords.words(idioma))
        except:
            self.stopwords = set(['el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'me', 'si', 'mi', 'ha', 'muy', 'ya', 'más', 'del', 'las', 'una', 'está', 'como', 'todo', 'pero', 'bien', 'así', 'al'])
        
        # Agregar stopwords personalizadas para redes sociales
        self.stopwords.update(['rt', 'via', 'http', 'https', 'www', 'com', 'org'])
        
        # Patrones de análisis
        self.emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        
    def analizar_posts(self, posts: List, nombre_competidor: str = "Competidor") -> CompetitorAnalysis:
        """Analiza una lista de posts y genera insights"""
        try:
            logger.info(f"Iniciando análisis de {len(posts)} posts de {nombre_competidor}")
            
            if not posts:
                logger.warning("No hay posts para analizar")
                return self._crear_analisis_vacio(nombre_competidor)
            
            # Análisis de hashtags
            hashtags_counter = self._analizar_hashtags(posts)
            
            # Análisis de palabras clave
            palabras_clave = self._analizar_palabras_clave(posts)
            
            # Análisis de emojis
            emojis_counter = self._analizar_emojis(posts)
            
            # Análisis de tipos de contenido
            tipos_contenido = self._analizar_tipos_contenido(posts)
            
            # Análisis de horarios
            horarios = self._analizar_horarios_publicacion(posts)
            
            # Análisis de texto
            longitud_promedio = self._calcular_longitud_promedio(posts)
            sentimiento_promedio = self._analizar_sentimiento(posts)
            
            # Análisis de colores (si hay imágenes)
            colores_dominantes = self._analizar_colores_dominantes(posts)
            
            # Análisis de temas
            temas_principales = self._identificar_temas_principales(posts)
            
            # Análisis de engagement
            patrones_engagement = self._analizar_engagement(posts)
            
            # Posts destacados
            posts_destacados = self._identificar_posts_destacados(posts)
            
            # Crear insights
            insights = ContentInsight(
                hashtags_mas_usados=hashtags_counter.most_common(10),
                palabras_clave=palabras_clave.most_common(15),
                emojis_mas_usados=emojis_counter.most_common(10),
                tipos_contenido=tipos_contenido,
                horarios_publicacion=horarios,
                longitud_promedio_texto=longitud_promedio,
                sentimiento_promedio=sentimiento_promedio,
                colores_dominantes=colores_dominantes,
                temas_principales=temas_principales,
                patrones_engagement=patrones_engagement
            )
            
            # Generar recomendaciones
            recomendaciones = self._generar_recomendaciones(insights, posts)
            
            # Crear análisis completo
            analisis = CompetitorAnalysis(
                nombre_competidor=nombre_competidor,
                total_posts=len(posts),
                plataformas=list(set([post.plataforma for post in posts if hasattr(post, 'plataforma')])),
                insights=insights,
                posts_destacados=posts_destacados,
                recomendaciones=recomendaciones
            )
            
            logger.info(f"Análisis completado para {nombre_competidor}")
            return analisis
            
        except Exception as e:
            logger.error(f"Error al analizar posts de {nombre_competidor}: {e}")
            return self._crear_analisis_vacio(nombre_competidor)
    
    def _analizar_hashtags(self, posts: List) -> Counter:
        """Analiza y cuenta hashtags"""
        hashtags = []
        for post in posts:
            if hasattr(post, 'hashtags') and post.hashtags:
                hashtags.extend(post.hashtags)
            elif hasattr(post, 'texto'):
                # Extraer hashtags del texto si no están en campo separado
                hashtags_en_texto = re.findall(r'#\w+', post.texto.lower())
                hashtags.extend(hashtags_en_texto)
        
        return Counter(hashtags)
    
    def _analizar_palabras_clave(self, posts: List) -> Counter:
        """Analiza palabras clave más frecuentes"""
        palabras = []
        
        for post in posts:
            texto = ""
            if hasattr(post, 'texto') and post.texto:
                texto = post.texto
            
            if texto:
                # Limpiar texto
                texto_limpio = self._limpiar_texto(texto)
                
                # Tokenizar
                tokens = word_tokenize(texto_limpio.lower())
                
                # Filtrar palabras
                palabras_filtradas = [
                    self.stemmer.stem(palabra) 
                    for palabra in tokens 
                    if palabra.isalpha() 
                    and len(palabra) > 3 
                    and palabra not in self.stopwords
                ]
                
                palabras.extend(palabras_filtradas)
        
        return Counter(palabras)
    
    def _analizar_emojis(self, posts: List) -> Counter:
        """Analiza emojis más utilizados"""
        emojis = []
        
        for post in posts:
            if hasattr(post, 'texto') and post.texto:
                emojis_en_texto = self.emoji_pattern.findall(post.texto)
                emojis.extend(emojis_en_texto)
        
        return Counter(emojis)
    
    def _analizar_tipos_contenido(self, posts: List) -> Dict[str, int]:
        """Analiza distribución de tipos de contenido"""
        tipos = defaultdict(int)
        
        for post in posts:
            if hasattr(post, 'tipo_contenido'):
                tipos[post.tipo_contenido] += 1
            elif hasattr(post, 'url_imagen') and post.url_imagen:
                tipos['imagen'] += 1
            elif hasattr(post, 'url_video') and post.url_video:
                tipos['video'] += 1
            else:
                tipos['texto'] += 1
        
        return dict(tipos)
    
    def _analizar_horarios_publicacion(self, posts: List) -> Dict[str, int]:
        """Analiza horarios de publicación"""
        horarios = defaultdict(int)
        
        for post in posts:
            if hasattr(post, 'fecha_publicacion') and post.fecha_publicacion:
                try:
                    # Intentar parsear fecha
                    fecha = datetime.fromisoformat(post.fecha_publicacion.replace('Z', '+00:00'))
                    hora = fecha.hour
                    
                    # Categorizar por franjas horarias
                    if 6 <= hora < 12:
                        franja = "Mañana (6-12h)"
                    elif 12 <= hora < 18:
                        franja = "Tarde (12-18h)"
                    elif 18 <= hora < 24:
                        franja = "Noche (18-24h)"
                    else:
                        franja = "Madrugada (0-6h)"
                    
                    horarios[franja] += 1
                    
                except:
                    horarios["Sin información"] += 1
            else:
                horarios["Sin información"] += 1
        
        return dict(horarios)
    
    def _calcular_longitud_promedio(self, posts: List) -> float:
        """Calcula longitud promedio del texto"""
        longitudes = []
        
        for post in posts:
            if hasattr(post, 'texto') and post.texto:
                longitudes.append(len(post.texto))
        
        return sum(longitudes) / len(longitudes) if longitudes else 0
    
    def _analizar_sentimiento(self, posts: List) -> float:
        """Analiza sentimiento promedio de los posts"""
        sentimientos = []
        
        for post in posts:
            if hasattr(post, 'texto') and post.texto:
                try:
                    blob = TextBlob(post.texto)
                    sentimientos.append(blob.sentiment.polarity)
                except:
                    continue
        
        return sum(sentimientos) / len(sentimientos) if sentimientos else 0
    
    def _analizar_colores_dominantes(self, posts: List) -> List[str]:
        """Analiza colores dominantes en las imágenes"""
        colores = []
        
        for post in posts:
            if hasattr(post, 'url_imagen') and post.url_imagen:
                try:
                    color_dominante = self._extraer_color_dominante(post.url_imagen)
                    if color_dominante:
                        colores.append(color_dominante)
                except Exception as e:
                    logger.warning(f"Error al analizar color de imagen: {e}")
                    continue
        
        # Retornar colores más frecuentes
        color_counter = Counter(colores)
        return [color for color, _ in color_counter.most_common(5)]
    
    def _extraer_color_dominante(self, url_imagen: str) -> Optional[str]:
        """Extrae color dominante de una imagen"""
        try:
            response = requests.get(url_imagen, timeout=10)
            response.raise_for_status()
            
            # Abrir imagen
            imagen = Image.open(BytesIO(response.content))
            imagen = imagen.convert('RGB')
            
            # Redimensionar para acelerar procesamiento
            imagen = imagen.resize((50, 50))
            
            # Convertir a array numpy
            data = np.array(imagen)
            data = data.reshape((-1, 3))
            
            # Aplicar k-means para encontrar colores dominantes
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=1, random_state=42, n_init=10)
            kmeans.fit(data)
            
            # Obtener color dominante
            color_rgb = kmeans.cluster_centers_[0].astype(int)
            
            # Convertir a nombre de color aproximado
            return self._rgb_a_nombre_color(color_rgb)
            
        except Exception as e:
            logger.warning(f"Error al extraer color dominante: {e}")
            return None
    
    def _rgb_a_nombre_color(self, rgb: np.array) -> str:
        """Convierte RGB a nombre de color aproximado"""
        r, g, b = rgb
        
        # Colores básicos para clasificación
        colores = {
            'rojo': (255, 0, 0),
            'verde': (0, 255, 0),
            'azul': (0, 0, 255),
            'amarillo': (255, 255, 0),
            'morado': (128, 0, 128),
            'naranja': (255, 165, 0),
            'rosa': (255, 192, 203),
            'negro': (0, 0, 0),
            'blanco': (255, 255, 255),
            'gris': (128, 128, 128),
            'marrón': (165, 42, 42)
        }
        
        min_distancia = float('inf')
        color_mas_cercano = 'gris'
        
        for nombre, (cr, cg, cb) in colores.items():
            distancia = ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5
            if distancia < min_distancia:
                min_distancia = distancia
                color_mas_cercano = nombre
        
        return color_mas_cercano
    
    def _identificar_temas_principales(self, posts: List) -> List[str]:
        """Identifica temas principales usando clustering de palabras"""
        try:
            # Recopilar todo el texto
            textos = []
            for post in posts:
                if hasattr(post, 'texto') and post.texto:
                    textos.append(self._limpiar_texto(post.texto))
            
            if not textos:
                return []
            
            # Análisis simple basado en frecuencia de palabras
            palabras_clave = self._analizar_palabras_clave(posts)
            top_palabras = [palabra for palabra, _ in palabras_clave.most_common(10)]
            
            # Generar temas basados en palabras clave agrupadas
            temas = []
            
            # Temas comunes en marketing
            temas_marketing = {
                'producto': ['producto', 'servicio', 'calidad', 'precio', 'oferta'],
                'lifestyle': ['vida', 'estilo', 'familia', 'hogar', 'experiencia'],
                'tecnología': ['digital', 'online', 'app', 'web', 'innovación'],
                'promoción': ['descuento', 'promoción', 'venta', 'especial', 'gratis'],
                'comunidad': ['comunidad', 'equipo', 'cliente', 'persona', 'gente']
            }
            
            for tema, palabras_tema in temas_marketing.items():
                if any(palabra in top_palabras for palabra in palabras_tema):
                    temas.append(tema)
            
            return temas[:5] if temas else ['general']
            
        except Exception as e:
            logger.error(f"Error al identificar temas: {e}")
            return ['general']
    
    def _analizar_engagement(self, posts: List) -> Dict[str, float]:
        """Analiza patrones de engagement"""
        engagement_data = {
            'likes_promedio': 0,
            'comentarios_promedio': 0,
            'compartidos_promedio': 0,
            'engagement_rate': 0
        }
        
        likes_total = []
        comentarios_total = []
        compartidos_total = []
        
        for post in posts:
            if hasattr(post, 'likes') and post.likes is not None:
                likes_total.append(post.likes)
            if hasattr(post, 'comentarios') and post.comentarios is not None:
                comentarios_total.append(post.comentarios)
            if hasattr(post, 'compartidos') and post.compartidos is not None:
                compartidos_total.append(post.compartidos)
        
        if likes_total:
            engagement_data['likes_promedio'] = sum(likes_total) / len(likes_total)
        if comentarios_total:
            engagement_data['comentarios_promedio'] = sum(comentarios_total) / len(comentarios_total)
        if compartidos_total:
            engagement_data['compartidos_promedio'] = sum(compartidos_total) / len(compartidos_total)
        
        # Calcular engagement rate aproximado
        total_interacciones = engagement_data['likes_promedio'] + engagement_data['comentarios_promedio'] + engagement_data['compartidos_promedio']
        engagement_data['engagement_rate'] = total_interacciones
        
        return engagement_data
    
    def _identificar_posts_destacados(self, posts: List) -> List[Dict]:
        """Identifica posts con mejor engagement"""
        posts_con_engagement = []
        
        for post in posts:
            engagement_score = 0
            
            if hasattr(post, 'likes') and post.likes:
                engagement_score += post.likes
            if hasattr(post, 'comentarios') and post.comentarios:
                engagement_score += post.comentarios * 2  # Comentarios valen más
            if hasattr(post, 'compartidos') and post.compartidos:
                engagement_score += post.compartidos * 3  # Compartir vale aún más
            
            if engagement_score > 0:
                posts_con_engagement.append({
                    'post': asdict(post) if hasattr(post, '__dict__') else vars(post),
                    'engagement_score': engagement_score
                })
        
        # Ordenar por engagement y tomar los top 3
        posts_con_engagement.sort(key=lambda x: x['engagement_score'], reverse=True)
        return posts_con_engagement[:3]
    
    def _generar_recomendaciones(self, insights: ContentInsight, posts: List) -> List[str]:
        """Genera recomendaciones basadas en el análisis"""
        recomendaciones = []
        
        # Recomendaciones de hashtags
        if insights.hashtags_mas_usados:
            top_hashtags = [tag for tag, _ in insights.hashtags_mas_usados[:5]]
            recomendaciones.append(f"Usar hashtags populares: {', '.join(top_hashtags)}")
        
        # Recomendaciones de horarios
        if insights.horarios_publicacion:
            mejor_horario = max(insights.horarios_publicacion, key=insights.horarios_publicacion.get)
            recomendaciones.append(f"Publicar en {mejor_horario} para mayor alcance")
        
        # Recomendaciones de longitud de texto
        if insights.longitud_promedio_texto > 0:
            if insights.longitud_promedio_texto < 100:
                recomendaciones.append("Considerar textos más largos para mayor engagement")
            elif insights.longitud_promedio_texto > 300:
                recomendaciones.append("Textos más concisos podrían ser más efectivos")
        
        # Recomendaciones de tipo de contenido
        if insights.tipos_contenido:
            tipo_mas_usado = max(insights.tipos_contenido, key=insights.tipos_contenido.get)
            if tipo_mas_usado == 'imagen':
                recomendaciones.append("Continuar enfocándose en contenido visual")
            elif tipo_mas_usado == 'video':
                recomendaciones.append("El video genera buen engagement, seguir usándolo")
        
        # Recomendaciones de sentimiento
        if insights.sentimiento_promedio > 0.3:
            recomendaciones.append("Mantener el tono positivo en las publicaciones")
        elif insights.sentimiento_promedio < -0.1:
            recomendaciones.append("Considerar un tono más positivo en el contenido")
        
        # Recomendaciones de emojis
        if insights.emojis_mas_usados:
            top_emojis = [emoji for emoji, _ in insights.emojis_mas_usados[:3]]
            recomendaciones.append(f"Incorporar emojis populares: {' '.join(top_emojis)}")
        
        # Recomendaciones de temas
        if insights.temas_principales:
            recomendaciones.append(f"Enfocar contenido en temas: {', '.join(insights.temas_principales)}")
        
        return recomendaciones
    
    def _limpiar_texto(self, texto: str) -> str:
        """Limpia texto para análisis"""
        # Remover URLs
        texto = re.sub(r'http\S+|www\S+|https\S+', '', texto, flags=re.MULTILINE)
        
        # Remover menciones y hashtags para análisis de palabras
        texto = re.sub(r'@\w+|#\w+', '', texto)
        
        # Remover caracteres especiales pero mantener espacios
        texto = re.sub(r'[^\w\s]', ' ', texto)
        
        # Remover espacios múltiples
        texto = re.sub(r'\s+', ' ', texto)
        
        return texto.strip()
    
    def _crear_analisis_vacio(self, nombre_competidor: str) -> CompetitorAnalysis:
        """Crea un análisis vacío cuando no hay datos"""
        insights_vacios = ContentInsight(
            hashtags_mas_usados=[],
            palabras_clave=[],
            emojis_mas_usados=[],
            tipos_contenido={},
            horarios_publicacion={},
            longitud_promedio_texto=0,
            sentimiento_promedio=0,
            colores_dominantes=[],
            temas_principales=[],
            patrones_engagement={}
        )
        
        return CompetitorAnalysis(
            nombre_competidor=nombre_competidor,
            total_posts=0,
            plataformas=[],
            insights=insights_vacios,
            posts_destacados=[],
            recomendaciones=["No hay suficientes datos para generar recomendaciones"]
        )
    
    def analizar_multiple_competidores(self, posts_por_competidor: Dict[str, List]) -> Dict[str, CompetitorAnalysis]:
        """Analiza múltiples competidores"""
        resultados = {}
        
        for nombre, posts in posts_por_competidor.items():
            logger.info(f"Analizando competidor: {nombre}")
            analisis = self.analizar_posts(posts, nombre)
            resultados[nombre] = analisis
        
        return resultados
    
    def generar_reporte_comparativo(self, analisis_competidores: Dict[str, CompetitorAnalysis]) -> Dict:
        """Genera un reporte comparativo de todos los competidores"""
        reporte = {
            'resumen_general': {},
            'mejores_practicas': [],
            'oportunidades': [],
            'benchmark_metricas': {}
        }
        
        if not analisis_competidores:
            return reporte
        
        # Agregar análisis comparativo
        total_posts = sum(analisis.total_posts for analisis in analisis_competidores.values())
        reporte['resumen_general']['total_posts_analizados'] = total_posts
        reporte['resumen_general']['total_competidores'] = len(analisis_competidores)
        
        # Hashtags más populares entre todos
        todos_hashtags = Counter()
        for analisis in analisis_competidores.values():
            for hashtag, count in analisis.insights.hashtags_mas_usados:
                todos_hashtags[hashtag] += count
        
        reporte['mejores_practicas'].append({
            'categoria': 'hashtags',
            'recomendacion': f"Hashtags más efectivos: {', '.join([tag for tag, _ in todos_hashtags.most_common(5)])}"
        })
        
        # Tipos de contenido más exitosos
        tipos_contenido_global = Counter()
        for analisis in analisis_competidores.values():
            for tipo, count in analisis.insights.tipos_contenido.items():
                tipos_contenido_global[tipo] += count
        
        if tipos_contenido_global:
            tipo_mas_popular = tipos_contenido_global.most_common(1)[0][0]
            reporte['mejores_practicas'].append({
                'categoria': 'contenido',
                'recomendacion': f"Tipo de contenido más usado: {tipo_mas_popular}"
            })
        
        return reporte
    
    def guardar_analisis(self, analisis: CompetitorAnalysis, filepath: str):
        """Guarda análisis en archivo JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(analisis), f, ensure_ascii=False, indent=2)
            logger.info(f"Análisis guardado en: {filepath}")
        except Exception as e:
            logger.error(f"Error al guardar análisis: {e}")
    
    def cargar_analisis(self, filepath: str) -> Optional[CompetitorAnalysis]:
        """Carga análisis desde archivo JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruir objetos
            insights_data = data['insights']
            insights = ContentInsight(**insights_data)
            
            analisis = CompetitorAnalysis(
                nombre_competidor=data['nombre_competidor'],
                total_posts=data['total_posts'],
                plataformas=data['plataformas'],
                insights=insights,
                posts_destacados=data['posts_destacados'],
                recomendaciones=data['recomendaciones']
            )
            
            logger.info(f"Análisis cargado desde: {filepath}")
            return analisis
            
        except Exception as e:
            logger.error(f"Error al cargar análisis: {e}")
            return None

# Función de utilidad
def analizar_competencia_completa(posts_por_competidor: Dict[str, List]) -> Dict:
    """Función de conveniencia para análisis completo de competencia"""
    analyzer = ContentAnalyzer()
    
    # Analizar cada competidor
    analisis_individual = analyzer.analizar_multiple_competidores(posts_por_competidor)
    
    # Generar reporte comparativo
    reporte_comparativo = analyzer.generar_reporte_comparativo(analisis_individual)
    
    return {
        'analisis_individual': analisis_individual,
        'reporte_comparativo': reporte_comparativo
    }

if __name__ == "__main__":
    # Ejemplo de uso
    from social_scraper import Post
    
    # Posts de ejemplo para testing
    posts_ejemplo = [
        Post(
            plataforma="instagram",
            url_post="https://instagram.com/p/example1",
            texto="¡Nuevo producto disponible! 🚀 #innovation #tech #startup",
            hashtags=["#innovation", "#tech", "#startup"],
            tipo_contenido="imagen",
            likes=150,
            comentarios=25
        ),
        Post(
            plataforma="facebook",
            url_post="https://facebook.com/post/example2",
            texto="Compartiendo tips de productividad para empresarios 💼 #business #tips",
            hashtags=["#business", "#tips"],
            tipo_contenido="texto",
            likes=89,
            comentarios=12
        )
    ]
    
    analyzer = ContentAnalyzer()
    analisis = analyzer.analizar_posts(posts_ejemplo, "Competidor Ejemplo")
    
    print(f"Análisis completado para: {analisis.nombre_competidor}")
    print(f"Total posts analizados: {analisis.total_posts}")
    print(f"Hashtags más usados: {analisis.insights.hashtags_mas_usados}")
    print(f"Recomendaciones: {analisis.recomendaciones}")