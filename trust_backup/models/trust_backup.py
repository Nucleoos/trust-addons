# -*- encoding: utf-8 -*-
###############################################################################
#                                                                             #
# Copyright (C) 2015 Trustcode - www.trustcode.com.br                         #
#              Danimar Ribeiro <danimaribeiro@gmail.com>                      #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU Affero General Public License as published by #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

from openerp import models, fields, api
from openerp.exceptions import Warning
from boto.s3.connection import S3Connection
from boto.s3.key import Key
import socket
import os
import time
import odoorpc
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


def execute(connector, method, *args):
    res = False
    try:
        res = getattr(connector, method)(*args)
    except socket.error as e:
        raise e
    return res


class BackupExecuted(models.Model):
    _name = 'backup.executed'
    _order = 'backup_date'

    def _generate_s3_link(self):
        return self.s3_id

    name = fields.Char('Arquivo', size=100)
    configuration_id = fields.Many2one('trust.backup', string="Configuração")
    backup_date = fields.Datetime(string="Data")
    local_path = fields.Char(string="Caminho Local", readonly=True)
    s3_id = fields.Char(string="S3 Id", readonly=True)
    s3_url = fields.Char("Link S3", compute='_generate_s3_link', readonly=True)
    state = fields.Selection(
        string="Estado", default='not_started',
        selection=[('not_started', 'Não iniciado'),
                   ('executing', 'Executando'),
                   ('sending', 'Enviando'),
                   ('error', 'Erro'), ('concluded', 'Concluído')])


class TrustBackup(models.Model):
    _name = 'trust.backup'

    @api.multi
    @api.depends('interval', 'database_name')
    def name_get(self):
        result = []
        for backup in self:
            result.append(
                (backup.id,
                 backup.database_name +
                 " - " +
                 backup.interval))
        return result

    def _get_total_backups(self):
        for item in self:
            item.backup_count = self.env['backup.executed'].search_count(
                [('configuration_id', '=', item.id)])

    host = fields.Char(string="Endereço", size=200, default='localhost')
    port = fields.Char(string="Porta", size=10, default='8069')
    database_name = fields.Char(string='Banco de dados', size=100)
    admin_password = fields.Char(string='Senha Admin', size=100)
    interval = fields.Selection(
        string=u"Período",
        selection=[('hora', '1 hora'), ('seis', '6 horas'),
                   ('doze', '12 horas'), ('diario', u'Diário')])

    send_to_s3 = fields.Boolean('Enviar Amazon S3 ?')
    aws_access_key = fields.Char(string="Chave API S3", size=100)
    aws_secret_key = fields.Char(string="Chave Secreta API S3", size=100)
    backup_dir = fields.Char(string=u"Diretório", size=300)

    next_backup = fields.Datetime(string=u"Próximo Backup")
    backup_count = fields.Integer(
        string=u"Nº Backups",
        compute='_get_total_backups')

    _defaults = {
        'backup_dir': '/opt/backups/database/',
        'host': lambda *a: 'localhost',
        'port': lambda *a: '8069'
    }

    def _set_next_backup(self):
        if self.interval == 'hora':
            self.next_backup = datetime.now() + timedelta(hours=1)
        elif self.interval == 'seis':
            self.next_backup = datetime.now() + timedelta(hours=6)
        elif self.interval == 'doze':
            self.next_backup = datetime.now() + timedelta(hours=12)
        else:
            self.next_backup = datetime.now() + timedelta(days=1)

    @api.multi
    def execute_backup(self):
        try:
            self.write({'next_backup': datetime.now()})
            self.schedule_backup()
        except Exception:
            _logger.error('Erro ao efetuar backup', exc_info=True)
            raise Warning('Erro ao executar backup - Verifique o log de erros')

    @api.model
    def schedule_backup(self):
        confs = self.search([])
        for rec in confs:

            if rec.next_backup:
                next_backup = datetime.strptime(
                    rec.next_backup,
                    '%Y-%m-%d %H:%M:%S')
            else:
                next_backup = datetime.now()
            if next_backup < datetime.now():

                odoo = odoorpc.ODOO(
                    rec.host,
                    protocol='jsonrpc',
                    port=rec.port,
                    timeout=1200)

                try:
                    if not os.path.isdir(rec.backup_dir):
                        os.makedirs(rec.backup_dir)
                except:
                    raise
                dump = odoo.db.dump(rec.admin_password, rec.database_name)
                zip_name = '%s_%s.zip' % (rec.database_name,
                                          time.strftime('%Y%m%d_%H_%M_%S'))
                zip_file = '%s/%s' % (rec.backup_dir, zip_name)

                with open(zip_file, 'wb') as dump_zip:
                    dump_zip.write(dump.read())
                    dump_zip.close()

                backup_env = self.env['backup.executed']

                if rec.send_to_s3:
                    key = rec.send_for_amazon_s3(zip_file, zip_name,
                                                 rec.database_name)
                    loc = ''
                    if not key:
                        key = 'Erro ao enviar para o Amazon S3'
                        loc = zip_file
                    else:
                        loc = 'https://s3.amazonaws.com/%s_bkp_pelican/%s' % (
                            rec.database_name, key
                        )
                    backup_env.create({'backup_date': datetime.now(),
                                       'configuration_id': rec.id,
                                       's3_id': key, 'name': zip_name,
                                       'state': 'concluded',
                                       'local_path': loc})
                    if key:
                        os.remove(zip_file)
                else:
                    backup_env.create(
                        {'backup_date': datetime.now(), 'name': zip_name,
                         'configuration_id': rec.id, 'state': 'concluded',
                         'local_path': zip_file})
                rec._set_next_backup()

    def send_for_amazon_s3(self, file_to_send, name_to_store, database):
        try:
            if self.aws_access_key and self.aws_secret_key:
                access_key = self.aws_access_key
                secret_key = self.aws_secret_key

                conexao = S3Connection(access_key, secret_key)
                bucket_name = '%s_bkp_pelican' % database
                bucket = conexao.create_bucket(bucket_name)

                k = Key(bucket)
                k.key = name_to_store
                k.set_contents_from_filename(file_to_send)
                return k.key
            else:
                _logger.error(
                    u'Configurações do Amazon S3 não setadas, \
                    pulando armazenamento de backup')
        except Exception:
            _logger.error('Erro ao enviar dados para S3', exc_info=True)
