# -*- encoding: utf-8 -*-
# © 2016 Alessandro Fernandes Martini, Trustcode
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import fields, models


class project_category(models.Model):
    _inherit = "project.category"

    color = fields.Integer(string="Cor")
