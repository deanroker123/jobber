include ../head.mk

PKGREL := $(shell cat pkgrel)
PLATFORM = x86_64
PACKAGING_SUBDIR = centos_6
PKGFILE ?= jobber-${VERSION}-${PKGREL}.el6.centos.${PLATFORM}.rpm
PKGFILE_DEPS = jobber.spec
PKGFILE_VM_PATH = jobber-${VERSION}-${PKGREL}.${PLATFORM}.rpm
INSTALL_PKG_CMD = sudo yum install -y ${PKGFILE}
DOCKER_IMAGE_NAME = jobber/centos6.7_build_rpm

.PHONY : pkg-local
pkg-local : jobber.spec ${WORK_DIR}/${SRC_TARFILE}
	# make RPM tree
	mkdir -p "${WORK_DIR}" \
		 "${WORK_DIR}/BUILD" \
                 "${WORK_DIR}/RPMS" \
                 "${WORK_DIR}/RPMS/${PLATFORM}" \
                 "${WORK_DIR}/SOURCES" \
                 "${WORK_DIR}/SPECS" \
                 "${WORK_DIR}/SRPMS"
	cp "$<" "${WORK_DIR}/SPECS"
	
	# copy sources
	cp "${WORK_DIR}/${SRC_TARFILE}" \
		se_policy/* \
		jobber_init "${WORK_DIR}/SOURCES/"
	
	# build RPMs
	cd "${WORK_DIR}/SPECS" && rpmbuild -bb \
		--define "_topdir ${abspath ${WORK_DIR}}" \
		--define "_pkg_version ${VERSION}" \
		--define "_pkg_release ${PKGREL}" \
		--define "_enable_debug_packages 0" \
		"$<"
	mkdir -p "${DESTDIR}"
	find "${WORK_DIR}/RPMS" -name '*.rpm' | xargs cp -t "${DESTDIR}"

include ../tail.mk