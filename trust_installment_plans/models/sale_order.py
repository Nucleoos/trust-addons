# -*- encoding: utf-8 -*-
###############################################################################
#                                                                             #
# Copyright (C) 2015 TrustCode - www.trustcode.com.br                         #
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

from datetime import datetime

from openerp import api, fields, models
from openerp.exceptions import Warning
from openerp.tools.translate import _


class PaymentInstallment(models.Model):
    _name = 'payment.installment'

    due_date = fields.Date(u'Data de vencimento')
    payment_mode_id = fields.Many2one('payment.mode',
                                      string=u"Forma de pagamento")
    amount = fields.Float(u'Total', digits=(18, 2))

    sale_order_id = fields.Many2one('sale.order',
                                    string=u"Pedido de Venda")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_installment_ids = fields.One2many('payment.installment',
                                              'sale_order_id',
                                              string=u"Parcelamento")

    @api.one
    def generate_installment(self):
        if self.payment_term:
            values = self.payment_term.compute(self.amount_total)
            for item in self.payment_installment_ids:
                item.unlink()

            for item in values[0]:
                print item
                parcel = {'due_date': datetime.strptime(item[0], '%Y-%m-%d'),
                          'payment_mode_id': self.payment_mode_id.id,
                          'amount': item[1], 'sale_order_id': self.id}
                self.env['payment.installment'].create(parcel)

        else:
            Warning(_(u'Choose a payment term first'))
