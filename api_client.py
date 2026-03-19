# api_client.py
import aiohttp
import uuid
from loguru import logger
from typing import Optional, Dict, Any

class BaseAPIClient:
    """Cliente base con configuración común"""
    def __init__(self, backend_url: str, timeout: int = 10):
        self.backend_url = backend_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    async def _post(self, endpoint: str, data: dict) -> Dict[str, Any]:
        """Método helper para POST requests"""
        url = f"{self.backend_url}{endpoint}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=data) as resp:
                if resp.status in [200, 201]:
                    return await resp.json()
                error_text = await resp.text()
                logger.error(f"❌ API Error {resp.status}: {error_text}")
                raise Exception(f"API Error: {resp.status}")

    async def _patch(self, endpoint: str, data: dict) -> Dict[str, Any]:
        """Método helper para PATCH requests"""
        url = f"{self.backend_url}{endpoint}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.patch(url, json=data) as resp:
                if resp.status in [200, 201]:
                    return await resp.json()
                error_text = await resp.text()
                logger.error(f"❌ API Error {resp.status}: {error_text}")
                raise Exception(f"API Error: {resp.status}")


class CallsAPIClient(BaseAPIClient):
    """Cliente para el módulo de calls"""
    
    def __init__(self, backend_url: str):
        super().__init__(backend_url)
        self.current_call_sid: Optional[str] = None
        self.current_call_id: Optional[int] = None
        self.current_client_id: Optional[int] = None

    def generate_call_sid(self) -> str:
        """Genera un callSid único para pruebas web"""
        call_sid = f"WEB_TEST_{uuid.uuid4().hex[:12].upper()}"
        logger.info(f"📞 CallSID generado: {call_sid}")
        return call_sid

    async def register_call(self) -> Optional[Dict[str, Any]]:
        """Registra una nueva llamada al inicio de la conexión"""
        self.current_call_sid = self.generate_call_sid()
        
        call_data = {
            "callSid": self.current_call_sid,
            "status": "started"
        }
        
        try:
            result = await self._post("/calls", call_data)
            self.current_call_id = result['id']
            logger.info(f"✅ Llamada registrada con ID: {self.current_call_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Error registrando llamada: {e}")
            return None

    async def update_status(self, status: str) -> bool:
        """Actualiza el estado de la llamada actual"""
        if not self.current_call_sid:
            logger.error("❌ No hay callSid activo")
            return False
        
        try:
            await self._patch(f"/calls/sid/{self.current_call_sid}/status", 
                            {"status": status})
            logger.info(f"✅ Estado actualizado: {status}")
            return True
        except Exception as e:
            logger.error(f"❌ Error actualizando estado: {e}")
            return False

    async def assign_client(self, client_id: int) -> bool:
        """Asigna un cliente a la llamada actual"""
        if not self.current_call_id:
            logger.error("❌ No hay callId activo")
            return False
        
        self.current_client_id = client_id
        
        try:
            await self._patch(f"/calls/{self.current_call_id}", 
                            {"client_id": client_id})
            logger.info(f"✅ Cliente {client_id} asignado a llamada")
            return True
        except Exception as e:
            logger.error(f"❌ Error asignando cliente: {e}")
            return False

    async def mark_service_created(self, service_id: int) -> bool:
        """Marca que se creó un servicio desde esta llamada"""
        if not self.current_call_id:
            logger.error("❌ No hay callId activo")
            return False
        
        try:
            await self._patch(f"/calls/{self.current_call_id}/mark-service",
                            {"service_id": service_id})
            logger.info(f"✅ Servicio {service_id} marcado en llamada")
            return True
        except Exception as e:
            logger.error(f"❌ Error marcando servicio: {e}")
            return False

    async def complete_call(self, duration: int = None) -> bool:
        """Marca la llamada como completada"""
        result = await self.update_status("completed")
        if result:
            logger.info(f"✅ Llamada {self.current_call_sid} completada")
        return result


class UsersAPIClient(BaseAPIClient):
    """Cliente para el módulo de usuarios/clientes"""
    
    async def check_user(self, phone: str) -> Dict[str, Any]:
        """Verifica si un usuario existe por teléfono"""
        clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
        return await self._post("/bot-clients/check", {"phone": clean_phone})

    async def register_user(self, phone: str, name: str) -> Dict[str, Any]:
        """Registra un nuevo usuario"""
        clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
        return await self._post("/bot-clients/register", {
            "phone": clean_phone,
            "name": name
        })


class AddressAPIClient(BaseAPIClient):
    """Cliente para el módulo de direcciones"""
    
    async def resolve_address(self, address_text: str) -> Dict[str, Any]:
        """Resuelve una dirección a coordenadas"""
        return await self._post("/bot-services/resolve-address", {
            "address_text": address_text
        })


class ServicesAPIClient(BaseAPIClient):
    """Cliente para el módulo de servicios"""
    
    def __init__(self, backend_url: str):
        super().__init__(backend_url, timeout=15)

    async def create_taxi_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un servicio de taxi"""
        return await self._post("/bot-services/create", service_data)