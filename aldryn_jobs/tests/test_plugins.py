from django.utils.translation import override
from django.contrib.auth.models import Group
from cms import api

from .base import JobsBaseTestCase


class TestAppConfigPluginsMixin(object):
    plugin_to_test = 'TextPlugin'
    plugin_params = {}

    def setUp(self):
        super(TestAppConfigPluginsMixin, self).setUp()
        self.plugin_page = self.create_plugin_page()
        self.placeholder = self.plugin_page.placeholders.all()[0]

    def create_plugin_page(self):
        page = api.create_page(
            title="Jobs plugin page en",
            template=self.template,
            language=self.language,
            parent=self.root_page,
            published=True)
        api.create_title('de', 'Jobs plugin page de', page,
                         slug='jobs-plugin-page-de')
        page.publish('en')
        page.publish('de')
        return page.reload()

    def _create_plugin(self, page, language, app_config, **plugin_params):
        """
        Create plugin of type self.plugin_to_test and plugin_params in
        given language to a page placeholder.
        Assumes that page has that translation.
        """
        placeholder = page.placeholders.all()[0]
        api.add_plugin(
            placeholder, self.plugin_to_test, language,
            app_config=app_config, **plugin_params)
        plugin = placeholder.get_plugins().filter(
            language=language)[0].get_plugin_instance()[0]
        plugin.save()
        page.publish(self.language)
        return plugin


class TestPluginFailuresWithDeletedAppHookMixin(object):
    """
    General test cases for 500 errors if app config or page wtih app hook
    was deleted.
    Relies on setUp which should prepare all plugins
    """

    def test_plugin_doesnt_break_page_if_configured_apphook_was_deleted(self):
        # delete apphooked page
        self.page.delete()

        for language_code in ('en', 'de'):
            with override(language_code):
                page_url_en = self.plugin_page.get_absolute_url()
            response = self.client.get(page_url_en)
            self.assertEqual(response.status_code, 200)

    def test_plugin_doesnt_break_page_for_su_if_apphook_was_deleted(self):
        # delete apphooked page
        self.page.delete()

        for language_code in ('en', 'de'):
            with override(language_code):
                page_url_en = '{0}?edit'.format(
                    self.plugin_page.get_absolute_url())

            login_result = self.client.login(
                username=self.super_user, password=self.super_user_password)
            self.assertEqual(login_result, True)

            response = self.client.get(page_url_en)
            self.assertEqual(response.status_code, 200)

    def test_plugin_does_not_breaks_page_if_job_config_was_deleted(self):
        # delete JobConfig
        self.app_config.delete()

        for language_code in ('en', 'de'):
            with override(language_code):
                page_url_en = self.plugin_page.get_absolute_url()
            response = self.client.get(page_url_en)
            self.assertEqual(response.status_code, 200)

    def test_plugin_doesnt_breaks_page_for_su_if_job_config_was_deleted(self):
        # delete JobConfig
        self.app_config.delete()

        for language_code in ('en', 'de'):
            with override(language_code):
                page_url_en = '{0}?edit'.format(
                    self.plugin_page.get_absolute_url())

            login_result = self.client.login(
                username=self.super_user, password=self.super_user_password)
            self.assertEqual(login_result, True)

            response = self.client.get(page_url_en)
            self.assertEqual(response.status_code, 200)

    def test_plugin_does_not_displays_error_message_to_non_super_users(self):
        # delete apphooked page
        self.page.delete()

        with override('en'):
            page_url = self.plugin_page.get_absolute_url()

        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'There is an error in plugin configuration: selected Job')

    def test_plugin_displays_error_message_to_super_users(self):
        # delete apphooked page
        self.page.delete()

        with override('en'):
            page_url = self.plugin_page.get_absolute_url()

        login_result = self.client.login(
            username=self.super_user, password=self.super_user_password)
        self.assertEqual(login_result, True)

        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'There is an error in plugin configuration: selected Job')


class TestNewsletterPlugin(TestAppConfigPluginsMixin,
                           TestPluginFailuresWithDeletedAppHookMixin,
                           JobsBaseTestCase):
    plugin_to_test = 'JobNewsletter'

    def setUp(self):
        super(TestNewsletterPlugin, self).setUp()
        self.default_group = Group.objects.get_or_create(
            name='Newsletter signup notifications')[0]
        # create default plugins to test against them
        self.create_plugin(
            page=self.plugin_page,
            language=self.language,
            app_config=self.app_config,
            mail_to_group=self.default_group,
            **self.plugin_params)
        #
        self.create_plugin(self.plugin_page, 'de', self.app_config,
                           mail_to_group=self.default_group)

    def create_plugin(self, page, language, app_config, mail_to_group=None,
                      **plugin_params):
        plugin = self._create_plugin(
            page, language, app_config, **plugin_params)
        if mail_to_group is not None:
            # we need to update plugin configuration model with correct group
            # it is located under it's own manager
            plugin.jobnewsletterregistrationplugin.mail_to_group.add(
                mail_to_group)
            plugin.save()
        return plugin

    # FIXME: should be changed after switch to app_config settings
    # for mailing etc.
    def test_newsletter_plugins_configured_with_different_groups(self):
        other_group = Group.objects.get_or_create(
            name='Newsletter signup notifications DE')[0]
        other_group_plugin = self.create_plugin(
            self.plugin_page, 'de', self.app_config,
            mail_to_group=other_group)
        placeholder = self.plugin_page.placeholders.all()[0]

        # test en plugin group equals to default_group
        plugin = placeholder.get_plugins().filter(language='en')[0]
        self.assertEqual(
            plugin.jobnewsletterregistrationplugin.mail_to_group.count(), 1)
        self.assertEqual(
            plugin.jobnewsletterregistrationplugin.mail_to_group.all()[0],
            self.default_group)

        # test de plugin group
        plugin = placeholder.get_plugins().filter(
            language='de').get(pk=other_group_plugin.pk)
        self.assertEqual(
            plugin.jobnewsletterregistrationplugin.mail_to_group.count(), 2)
        self.assertIn(
            other_group,
            plugin.jobnewsletterregistrationplugin.mail_to_group.all())

    def test_plugin_with_different_groups_does_not_breaks_page(self):
        other_group = Group.objects.get_or_create(
            name='Newsletter signup notifications DE')[0]
        self.create_plugin(
            self.plugin_page, 'de', self.app_config, mail_to_group=other_group)

        for language_code in ('en', 'de'):
            with override(language_code):
                page_url_en = self.plugin_page.get_absolute_url()
            response = self.client.get(page_url_en)
            self.assertEqual(response.status_code, 200)

    def test_plugin_with_deleted_group_does_not_breaks_page(self):
        self.default_group.delete()

        for language_code in ('en', 'de'):
            with override(language_code):
                page_url_en = self.plugin_page.get_absolute_url()
            response = self.client.get(page_url_en)
            self.assertEqual(response.status_code, 200)


class TestJobCategoriesListPlugin(TestAppConfigPluginsMixin,
                                  TestPluginFailuresWithDeletedAppHookMixin,
                                  JobsBaseTestCase):
    plugin_to_test = 'JobCategoriesList'

    def setUp(self):
        super(TestJobCategoriesListPlugin, self).setUp()
        # create plugin for both languages
        self.create_plugin(self.plugin_page, 'en', self.app_config)
        self.create_plugin(self.plugin_page, 'de', self.app_config)

    def create_plugin(self, page, language, app_config,
                      **plugin_params):
        plugin = self._create_plugin(
            page, language, app_config, **plugin_params)
        return plugin


class TestJobListPlugin(TestAppConfigPluginsMixin,
                        TestPluginFailuresWithDeletedAppHookMixin,
                        JobsBaseTestCase):
    plugin_to_test = 'JobList'

    def setUp(self):
        super(TestJobListPlugin, self).setUp()
        job_offer = self.create_default_job_offer(translated=True)
        self.create_plugin(self.plugin_page, 'en', self.app_config,
                           joboffers=job_offer)
        self.create_plugin(self.plugin_page, 'de', self.app_config,
                           joboffers=job_offer)

    def create_plugin(self, page, language, app_config, joboffers=None,
                      **plugin_params):
        plugin = self._create_plugin(
            page, language, app_config, **plugin_params)
        if joboffers is not None:
            # we need to update plugin configuration model with correct group
            # it is located under it's own manager
            plugin.joblistplugin.joboffers.add(
                joboffers)
            plugin.save()
        return plugin