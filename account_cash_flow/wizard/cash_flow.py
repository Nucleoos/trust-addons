# -*- coding: utf-8 -*-
# © 2016 Danimar Ribeiro, Trustcode
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import datetime
import openerp.addons.decimal_precision as dp
from openerp import api, fields, models


class CashFlowWizard(models.TransientModel):
    _name = 'account.cash.flow.wizard'

    start_date = fields.Date(string="Start Date", required=True,
                             default=fields.date.today())
    end_date = fields.Date(
        string="End Date", required=True,
        default=fields.date.today()+datetime.timedelta(6*365/12))
    start_amount = fields.Float(string="Initial value",
                                digits_compute=dp.get_precision('Account'))

    @api.multi
    def button_calculate(self):
        cashflow_id = self.env['account.cash.flow'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'start_amount': self.start_amount,
        })
        cashflow_id.action_calculate_report()

        dummy, action_id = self.env['ir.model.data'].get_object_reference(
            'account_cash_flow', 'account_cash_flow_report_action')
        vals = self.env['ir.actions.act_window'].browse(action_id).read()[0]
        vals['domain'] = [('cashflow_id', '=', cashflow_id.id)]
        vals['context'] = {'search_default_cashflow_id': cashflow_id.id}
        return vals