from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class HealthTests(TestCase):
    def test_health_publico_com_banco_acessivel(self):
        resposta = self.client.get(reverse('health'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'status': 'ok'})
        self.assertEqual(self.client.post(reverse('health')).status_code, 405)

    def test_falha_do_banco_retorna_503_sem_detalhes_internos(self):
        with patch('bibliotecapi.health.connection.cursor', side_effect=DatabaseError('caminho-privado')):
            resposta = self.client.get(reverse('health'))
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.json(), {'status': 'unavailable'})
