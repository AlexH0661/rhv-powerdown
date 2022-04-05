Name:           monitor_ups
Version:        0.1
Release:        1%{?dist}
Summary:        Monitor Eaton UPS and gracefully shutdown RHV cluster if UPS are on battery

License:        Apache 2.0
URL:            https://github.com/AlexH0661/rhv-powerdown
Source0:        

BuildRequires:  
Requires:       

%description


%prep
%autosetup


%build
%configure
%make_build


%install
%make_install


%files
%license add-license-file-here
%doc add-docs-here



%changelog
* Sun Mar 27 2022 Alexander Hussey <alex@HUSSDOGG.com>
- 
