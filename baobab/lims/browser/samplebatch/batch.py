from zope.schema import ValidationError

from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.ATContentTypes.lib import constraintypes

from bika.lims.browser import BrowserView
from baobab.lims.browser.project.util import SampleGeneration
from baobab.lims.browser.project import get_first_sampletype
from baobab.lims.browser.biospecimens.biospecimens import BiospecimensView


class BatchBiospecimensView(BiospecimensView):
    """ Biospecimens veiw from kit view.
    """
    def __init__(self, context, request):
        BiospecimensView.__init__(self, context, request, 'batch')
        self.context = context
        self.context_actions = {}

        # Filter biospecimens by project uid
        self.columns.pop('Project', None)
        # path = '/'.join(self.context.getPhysicalPath())
        for state in self.review_states:
            # state['contentFilter']['path'] = {'query': path, 'depth': 1}
            state['contentFilter']['getProjectUID'] = self.context.aq_parent.UID()
            state['contentFilter']['sort_on'] = 'sortable_title'
            state['columns'].remove('Project')

    def folderitems(self, full_objects=False):
        items = BiospecimensView.folderitems(self)
        out_items = []
        for item in items:
            if "obj" not in item:
                continue
            obj = item['obj']
            batch = obj.getField('Batch').get(obj)
            if batch:
                batch_uid = batch.UID()
                if batch_uid == self.context.UID():
                    out_items.append(item)
        return out_items


class EditView(BrowserView):

    template = ViewPageTemplateFile('templates/batch_edit.pt')

    def __call__(self):
        request = self.request
        context = self.context
        self.form = request.form

        if 'submitted' in request:
            try:
                self.validate_form_input()
            except ValidationError as e:
                self.form_error(e.message)
                return

            context.setConstrainTypesMode(constraintypes.DISABLED)
            portal_factory = getToolByName(context, 'portal_factory')

            folder = context.aq_parent
            batch = None
            if not folder.hasObject(context.getId()):
                batch = portal_factory.doCreate(context, context.id)
            else:
                batch = context

            old_qty = int(batch.Quantity or 0)
            new_qty = int(self.form.get('Quantity', 0))
            batch.processForm()
            self.create_samples(batch, self.form, new_qty - old_qty)

            obj_url = batch.absolute_url_path()
            request.response.redirect(obj_url)

            return

        return self.template()

    def validate_form_input(self):
        new_qty = int(self.form.get('Quantity', 0))
        old_qty = int(self.context.Quantity or 0)

        if new_qty <= 0:
            raise ValidationError('Quantity of samples cannot be zero or less than zero!')
        if new_qty < old_qty:
            raise ValidationError('New number of samples cannot be less than the number of samples already created!')

    def create_samples(self, context, form, num_samples):
        """Create samples from form
        """
        sample_type = get_first_sampletype(context)
        uc = getToolByName(context, 'uid_catalog')

        project_uid = form.get('Project_uid', '')
        project = uc(UID=project_uid)[0].getObject()

        samples_gen = SampleGeneration(form, project)

        samples = []
        for i in range(num_samples):
            sample = samples_gen.create_sample(None, sample_type, context)
            samples.append(sample)

        location_uid = form.get('StorageLocation_uid', '')
        storage = []
        if location_uid:
            location = uc(UID=location_uid)[0].getObject()
            if len(location.get_free_positions()) > 0:
                storage.append(location)

        if storage:
            samples_gen.store_samples(samples, storage)

        return samples

    def get_fields_with_visibility(self, visibility, mode=None):
        mode = mode if mode else 'edit'
        schema = self.context.Schema()
        fields = []
        for field in schema.fields():
            isVisible = field.widget.isVisible
            v = isVisible(self.context, mode, default='invisible', field=field)
            if v == visibility:
                fields.append(field)
        return fields

    def form_error(self, msg):
        self.context.plone_utils.addPortalMessage(msg)
        self.request.response.redirect(self.context.absolute_url())