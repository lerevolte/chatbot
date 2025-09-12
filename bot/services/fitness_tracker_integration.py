import logging
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import aiohttp
from sqlalchemy import select, and_

from database.models import User, CheckIn
from database.connection import get_session
from bot.config import settings

logger = logging.getLogger(__name__)

class FitnessTrackerBase(ABC):
    """Базовый класс для интеграции с фитнес-трекерами"""
    
    @abstractmethod
    async def authenticate(self, user_id: int, auth_code: str) -> bool:
        """Аутентификация пользователя"""
        pass
    
    @abstractmethod
    async def get_daily_data(self, user_id: int, date: datetime) -> Dict:
        """Получение данных за день"""
        pass
    
    @abstractmethod
    async def sync_data(self, user_id: int, days_back: int = 7) -> bool:
        """Синхронизация данных за период"""
        pass

class GoogleFitIntegration(FitnessTrackerBase):
    """Интеграция с Google Fit"""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com/fitness/v1"
        self.oauth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        
        # Эти данные нужно получить в Google Cloud Console
        self.client_id = getattr(settings, 'GOOGLE_FIT_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'GOOGLE_FIT_CLIENT_SECRET', None)
        self.redirect_uri = getattr(settings, 'GOOGLE_FIT_REDIRECT_URI', "http://localhost:8080/callback")
        
        # Хранилище токенов (в продакшене использовать Redis или БД)
        self.user_tokens = {}
    
    def get_auth_url(self, user_id: int) -> str:
        """Получает URL для авторизации в Google Fit"""
        if not self.client_id:
            return None
            
        scopes = [
            "https://www.googleapis.com/auth/fitness.activity.read",
            "https://www.googleapis.com/auth/fitness.body.read",
            "https://www.googleapis.com/auth/fitness.nutrition.read",
            "https://www.googleapis.com/auth/fitness.sleep.read"
        ]
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": str(user_id),
            "access_type": "offline",
            "prompt": "consent"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.oauth_url}?{query_string}"
    
    async def authenticate(self, user_id: int, auth_code: str) -> bool:
        """Обменивает код авторизации на токены"""
        if not self.client_id or not self.client_secret:
            logger.error("Google Fit credentials not configured")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "code": auth_code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
                
                async with session.post(self.token_url, data=data) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        self.user_tokens[user_id] = {
                            "access_token": tokens["access_token"],
                            "refresh_token": tokens.get("refresh_token"),
                            "expires_at": datetime.now() + timedelta(seconds=tokens["expires_in"])
                        }
                        
                        # Сохраняем токены в БД
                        await self.save_tokens(user_id, tokens)
                        logger.info(f"Successfully authenticated user {user_id} with Google Fit")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Failed to authenticate: {error}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error during Google Fit authentication: {e}")
            return False
    
    async def refresh_token(self, user_id: int) -> bool:
        """Обновляет access token используя refresh token"""
        tokens = self.user_tokens.get(user_id)
        if not tokens or not tokens.get("refresh_token"):
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "refresh_token": tokens["refresh_token"],
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token"
                }
                
                async with session.post(self.token_url, data=data) as response:
                    if response.status == 200:
                        new_tokens = await response.json()
                        tokens["access_token"] = new_tokens["access_token"]
                        tokens["expires_at"] = datetime.now() + timedelta(seconds=new_tokens["expires_in"])
                        return True
                        
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
        
        return False
    
    async def get_daily_data(self, user_id: int, date: datetime) -> Dict:
        """Получает данные о активности за день из Google Fit"""
        # Проверяем и обновляем токен если нужно
        tokens = self.user_tokens.get(user_id)
        if not tokens:
            logger.warning(f"No tokens for user {user_id}")
            return {}
        
        if datetime.now() >= tokens["expires_at"]:
            if not await self.refresh_token(user_id):
                return {}
        
        # Временные метки для запроса (начало и конец дня)
        start_time = int(datetime.combine(date.date(), datetime.min.time()).timestamp() * 1000)
        end_time = int(datetime.combine(date.date(), datetime.max.time()).timestamp() * 1000)
        
        data = {
            "steps": 0,
            "calories": 0,
            "distance": 0,
            "active_minutes": 0,
            "sleep_hours": 0,
            "heart_rate": [],
            "weight": None
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {tokens['access_token']}"}
                
                # Получаем шаги
                steps_data = {
                    "aggregateBy": [{
                        "dataTypeName": "com.google.step_count.delta",
                        "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
                    }],
                    "bucketByTime": {"durationMillis": 86400000},
                    "startTimeMillis": start_time,
                    "endTimeMillis": end_time
                }
                
                async with session.post(
                    f"{self.base_url}/users/me/dataset:aggregate",
                    headers=headers,
                    json=steps_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("bucket"):
                            for bucket in result["bucket"]:
                                for dataset in bucket.get("dataset", []):
                                    for point in dataset.get("point", []):
                                        for value in point.get("value", []):
                                            if value.get("intVal"):
                                                data["steps"] += value["intVal"]
                
                logger.info(f"Retrieved Google Fit data for user {user_id}: {data}")
                
        except Exception as e:
            logger.error(f"Error getting Google Fit data: {e}")
        
        return data
    
    async def sync_data(self, user_id: int, days_back: int = 7) -> bool:
        """Синхронизирует данные Google Fit с нашей БД"""
        try:
            async with get_session() as session:
                # Получаем пользователя
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return False
                
                # Синхронизируем данные за последние N дней
                for i in range(days_back):
                    date = datetime.now() - timedelta(days=i)
                    
                    # Получаем данные из Google Fit
                    fit_data = await self.get_daily_data(user_id, date)
                    
                    if fit_data and fit_data.get("steps"):
                        # Проверяем, есть ли уже чек-ин за этот день
                        result = await session.execute(
                            select(CheckIn).where(
                                and_(
                                    CheckIn.user_id == user.id,
                                    CheckIn.date >= datetime.combine(date.date(), datetime.min.time()),
                                    CheckIn.date <= datetime.combine(date.date(), datetime.max.time())
                                )
                            )
                        )
                        checkin = result.scalar_one_or_none()
                        
                        if not checkin:
                            checkin = CheckIn(
                                user_id=user.id,
                                date=date
                            )
                            session.add(checkin)
                        
                        # Обновляем данные
                        if fit_data.get("steps"):
                            checkin.steps = fit_data["steps"]
                        if fit_data.get("weight"):
                            checkin.weight = fit_data["weight"]
                        if fit_data.get("sleep_hours"):
                            checkin.sleep_hours = fit_data["sleep_hours"]
                        if fit_data.get("calories"):
                            checkin.calories_burned = fit_data["calories"]
                        if fit_data.get("active_minutes"):
                            checkin.active_minutes = fit_data["active_minutes"]
                        if fit_data.get("distance"):
                            checkin.distance_km = fit_data["distance"] / 1000
                        
                        # Добавляем в tracker_data
                        checkin.tracker_data = checkin.tracker_data or {}
                        checkin.tracker_data["google_fit"] = {
                            "synced_at": datetime.now().isoformat(),
                            "raw_data": fit_data
                        }
                
                await session.commit()
                logger.info(f"Successfully synced Google Fit data for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error syncing Google Fit data: {e}")
            return False
    
    async def save_tokens(self, user_id: int, tokens: Dict):
        """Сохраняет токены в БД"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.fitness_tokens = user.fitness_tokens or {}
                user.fitness_tokens["google_fit"] = {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens.get("refresh_token"),
                    "expires_at": (datetime.now() + timedelta(seconds=tokens["expires_in"])).isoformat()
                }
                await session.commit()

class FitnessIntegrationService:
    """Сервис управления интеграциями с фитнес-трекерами"""
    
    def __init__(self):
        self.integrations = {
            "google_fit": GoogleFitIntegration(),
            # В будущем можно добавить:
            # "apple_health": AppleHealthIntegration(),
            # "fitbit": FitbitIntegration(),
            # "strava": StravaIntegration(),
        }
        self.user_integrations = {}  # {user_id: ["google_fit", ...]}
    
    async def connect_service(self, user_id: int, service: str) -> Optional[str]:
        """Начинает процесс подключения сервиса"""
        if service not in self.integrations:
            return None
        
        integration = self.integrations[service]
        
        if service == "google_fit":
            return integration.get_auth_url(user_id)
        
        return None
    
    async def complete_connection(self, user_id: int, service: str, auth_code: str) -> bool:
        """Завершает подключение сервиса"""
        if service not in self.integrations:
            return False
        
        integration = self.integrations[service]
        success = await integration.authenticate(user_id, auth_code)
        
        if success:
            if user_id not in self.user_integrations:
                self.user_integrations[user_id] = []
            if service not in self.user_integrations[user_id]:
                self.user_integrations[user_id].append(service)
            
            # Сохраняем в БД
            await self.save_user_integration(user_id, service)
        
        return success
    
    async def sync_all(self, user_id: int) -> Dict[str, bool]:
        """Синхронизирует данные со всеми подключенными сервисами"""
        results = {}
        
        if user_id in self.user_integrations:
            for service in self.user_integrations[user_id]:
                integration = self.integrations.get(service)
                if integration:
                    results[service] = await integration.sync_data(user_id)
        
        return results
    
    async def get_aggregated_data(self, user_id: int, date: datetime) -> Dict:
        """Получает объединенные данные со всех подключенных сервисов"""
        aggregated = {
            "steps": 0,
            "calories": 0,
            "distance": 0,
            "active_minutes": 0,
            "sleep_hours": 0,
            "weight": None,
            "sources": []
        }
        
        if user_id in self.user_integrations:
            for service in self.user_integrations[user_id]:
                integration = self.integrations.get(service)
                if integration:
                    data = await integration.get_daily_data(user_id, date)
                    if data:
                        # Берем максимальное значение из всех источников
                        aggregated["steps"] = max(aggregated["steps"], data.get("steps", 0))
                        aggregated["calories"] = max(aggregated["calories"], data.get("calories", 0))
                        aggregated["distance"] = max(aggregated["distance"], data.get("distance", 0))
                        aggregated["active_minutes"] = max(aggregated["active_minutes"], data.get("active_minutes", 0))
                        
                        # Для веса и сна берем последнее ненулевое значение
                        if data.get("weight"):
                            aggregated["weight"] = data["weight"]
                        if data.get("sleep_hours"):
                            aggregated["sleep_hours"] = data["sleep_hours"]
                        
                        aggregated["sources"].append(service)
        
        return aggregated
    
    async def save_user_integration(self, user_id: int, service: str):
        """Сохраняет информацию о подключенной интеграции"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.connected_services = user.connected_services or []
                if service not in user.connected_services:
                    user.connected_services.append(service)
                await session.commit()
    
    async def load_user_integrations(self):
        """Загружает информацию о подключенных интеграциях из БД"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.connected_services.isnot(None))
            )
            users = result.scalars().all()
            
            for user in users:
                if user.connected_services:
                    self.user_integrations[user.telegram_id] = user.connected_services
                    
        logger.info(f"Loaded integrations for {len(self.user_integrations)} users")