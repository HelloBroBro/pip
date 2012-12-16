import pkg_resources
from pip.basecommand import Command
from pip.exceptions import DistributionNotFound, BestVersionAlreadyInstalled
from pip.index import PackageFinder
from pip.log import logger
from pip.req import InstallRequirement
from pip.util import get_installed_distributions, dist_is_editable
from pip.cmdoptions import make_option_group, index_group


class ListCommand(Command):
    name = 'list'
    usage = '%prog [OPTIONS]'
    summary = 'List all currently installed packages.'

    def __init__(self, *args, **kw):
        super(ListCommand, self).__init__(*args, **kw)


        cmd_opts = self.cmd_opts

        cmd_opts.add_option(
            '-l', '--local',
            action='store_true',
            default=False,
            help='If in a virtualenv, do not report globally-installed packages')
        cmd_opts.add_option(
            '-o', '--outdated',
            action='store_true',
            default=False,
            help='Output all currently installed outdated packages to stdout (excluding editables)')
        cmd_opts.add_option(
            '-u', '--uptodate',
            action='store_true',
            default=False,
            help='Output all currently installed uptodate packages to stdout (excluding editables)')
        cmd_opts.add_option(
            '-e', '--editables',
            action='store_true',
            default=False,
            help='Output all currently installed editable packages to stdout')

        index_opts = make_option_group(index_group, self.parser)

        self.parser.insert_option_group(0, index_opts)
        self.parser.insert_option_group(0, cmd_opts)


    def _build_package_finder(self, options, index_urls):
        """
        Create a package finder appropriate to this list command.
        """
        return PackageFinder(find_links=options.find_links,
                             index_urls=index_urls,
                             use_mirrors=options.use_mirrors,
                             mirrors=options.mirrors)

    def run(self, options, args):
        if options.outdated:
            self.run_outdated(options)
        elif options.uptodate:
            self.run_uptodate(options)
        elif options.editables:
            self.run_editables(options)
        else:
            self.run_listing(options)

    def run_outdated(self, options):
        for dist, remote_version_raw, remote_version_parsed in self.find_packages_latests_versions(options):
            if remote_version_parsed > dist.parsed_version:
                logger.notify('%s (CURRENT: %s LATEST: %s)' % (dist.project_name,
                    dist.version, remote_version_raw))

    def find_packages_latests_versions(self, options):
        index_urls = [options.index_url] + options.extra_index_urls
        if options.no_index:
            logger.notify('Ignoring indexes: %s' % ','.join(index_urls))
            index_urls = []

        dependency_links = []
        for dist in get_installed_distributions(local_only=options.local):
            if dist.has_metadata('dependency_links.txt'):
                dependency_links.extend(
                    dist.get_metadata_lines('dependency_links.txt'),
                )

        finder = self._build_package_finder(options, index_urls)
        finder.add_dependency_links(dependency_links)

        installed_packages = get_installed_distributions(local_only=options.local, include_editables=False)
        for dist in installed_packages:
            req = InstallRequirement.from_line(dist.key, None)
            try:
                link = finder.find_requirement(req, True)

                # If link is None, means installed version is most up-to-date
                if link is None:
                    continue
            except DistributionNotFound:
                continue
            except BestVersionAlreadyInstalled:
                remote_version = req.installed_version
            else:
                # It might be a good idea that link or finder had a public method
                # that returned version
                remote_version = finder._link_package_versions(link, req.name)[0]
                remote_version_raw = remote_version[2]
                remote_version_parsed = remote_version[0]
            yield dist, remote_version_raw, remote_version_parsed

    def run_listing(self, options):
        installed_packages = get_installed_distributions(local_only=options.local)
        self.output_package_listing(installed_packages)

    def run_editables(self, options):
        installed_packages = get_installed_distributions(local_only=options.local, editables_only=True)
        self.output_package_listing(installed_packages)

    def output_package_listing(self, installed_packages):
        for dist in installed_packages:
            line = '%s (%s)' % (dist.project_name, dist.version)
            if dist_is_editable(dist):
                line += ' editable src at %s' % dist.location
            logger.notify(line)

    def run_uptodate(self, options):
        uptodate = []
        for dist, remote_version_raw, remote_version_parsed in self.find_packages_latests_versions(options):
            if dist.parsed_version == remote_version_parsed:
                uptodate.append(dist)
        self.output_package_listing(uptodate)

