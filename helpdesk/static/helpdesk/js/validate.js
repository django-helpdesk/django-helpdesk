//TODO: 'High Performing' is not a type of property -- will need to add an array of 'high performing' types.

/* Variables */

var key = {
    affordable_boolean: 'e_is_affordable_housing',
    affordable_list: 'e_type_affordable_housing',
//LOCAL    affordable_boolean: 'is_affordable_housing',
//LOCAL    affordable_list: 'type_affordable_housing',
    acp_list: 'e_acp_type',
    property_list: 'e_property_type',
//LOCAL	property_list: 'property_type',
    pathway_list: 'e_pathway',
};
var id = {
    affordable_boolean: '#id_' + key.affordable_boolean,
    affordable_list: '#id_' + key.affordable_list,
    acp_list: '#id_' + key.acp_list,
    property_list: '#id_' + key.property_list,
    pathway_list: '#id_' + key.pathway_list,
};
var group = {
    affordable_boolean: '#id_group_' + key.affordable_boolean,
    affordable_list: '#id_group_' + key.affordable_list,
    acp_list: '#id_group_' + key.acp_list,
};
var high_perf = ['Adult Education','Ambulatory Surgical Center','Multifamily Housing','Automobile Dealership','Bank Branch','Bar/Nightclub','Barracks','Courthouse','College/University','Convenience Store with Gas Station','Convenience Store without Gas Station','Financial Office','Data Center','Drinking Water Treatment & Distribution','Enclosed Mall','Office','Fast Food Restaurant','Food Sales','Food Service','Hospital (General Medical & Surgical)','Hotel','Laboratory','Lifestyle Center','Medical Office','Other - Education','Other - Lodging/Residential','Other - Mall','Other - Restaurant/Bar','Other - Specialty Hospital','Outpatient Rehabilitation/Physical Therapy','Pre-school/Daycare','Prison/Incarceration','Residence Hall/Dormitory','Residential Care Facility','Restaurant','Retail Store','Self-Storage Facility','Senior Care Community (also know as Senior Livi Community)','Strip Mall','Supermarket/Grocery Store','Urgent Care/Clinic/Other Outpatient','Veterinary Office','Vocational School','Wastewater Treatment Plant','Wholesale Club/Supercenter']

/* Alerts */

var alertMsg1 = 'This property type is not eligible for the Standard Target Pathway, please select another pathway.';
var alertMsg2 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS/55/">FAQ</a>.';
var alertMsg3 = 'This property type is not eligible for the Extended Deep Energy Retrofit ACP Option, please select another pathway.'
var alertMsg4 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS/55/">FAQ</a>'
var alertMsg5 = 'We are unable to accept ACPs through this page at this time. Please check back later.'

/* This field apperas if "Pathway" = "Standard Target Pathway" AND ("Primary Property Type - Portfolio Manager Calculated" NOT IN High PErformance List) */
jQuery.validator.addMethod('alert1', function (value, element, param) {
    return this.optional(element) || !($(param.path).val() == 'Standard Target Pathway' && ($.inArray(value, high_perf) == -1));
}, alertMsg1);

jQuery.validator.addMethod('alert2', function (value, element) {
    var ok = this.optional(element) || value != 'Prescriptive Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg2);

/*  This field appears
    if "ACP Option" =  "Extended Deep Energy Retrofit"
    AND ("Affordable Housing/Rent Controlled?" = FALSE
    OR ("Primary Property Type - Portfolio Manager Calculated" != "College/University" OR "Hospital").
    If this alert text appears the user should not be able to submit the form, until they select another pathway */
jQuery.validator.addMethod('alert3', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( !$(param.affordable).prop('checked') || ($(param.prop).val() != "College/University" || $(param.prop).val() != "Hospital")) );
}, alertMsg3);

/*   if "ACP Option" =  "Extended Deep Energy Retrofit"
    AND ("Affordable Housing/Rent Controlled?" = TRUE
    OR ("Primary Property Type - Portfolio Manager Calculated" = "College/University" OR "Hospital").
    If this alert text appears the user should not be able to submit the form, until they select another pathway */
jQuery.validator.addMethod('alert4', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( $(param.affordable).prop('checked') || ($(param.prop).val() == "College/University" || $(param.prop).val() == "Hospital")) );
}, alertMsg4);

jQuery.validator.addMethod('alert5', function (value, element) {
    var ok =  this.optional(element) || value != 'Alternative Compliance Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg5);


/* Validations */

var form_validator = $('#ticket_submission_form').validate({
    ignore: '.error-okay',
    rules: {
        [key.pathway_list]: {
            alert2: true,
            alert5: true
        },
        [key.property_list]: {
            alert1: {
                param: {
                    path: id.pathway_list,
                    prop: id.property_list
                }
            }
        },
        [key.acp_list]: {
            alert3: {
                param: {
                    affordable: id.affordable_boolean,
                    prop: id.property_list
                }
            },
            alert4: {
                param: {
                    affordable: id.affordable_boolean,
                    prop: id.property_list
                }
            },
        }
    },
});


/* Hiding/showing elements based on other fields */

$(group.affordable_boolean).hide();
$(group.affordable_list).hide();
$(group.acp_list).hide();

$(id.property_list).change(function(){
    //Alert 3 must be checked when either of two fields changes
     if ($(id.acp_list).val() != '' && $(id.affordable_boolean).prop('checked'))
        form_validator.element(id.acp_list);

    //affordable_boolean field appears if the property type is Multifamily Housing
    if($(id.property_list).val() == "Multifamily Housing") {
        $(group.affordable_boolean).show();
    } else {
        $(group.affordable_boolean).hide();
        $(id.affordable_boolean).prop('checked', false);
    }

    //affordable_list field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.affordable_list).show();
    } else {
        $(group.affordable_list).hide();
        $(id.affordable_list).val('');
    }
   //High performing categories, hide Standard Target Pathway
    if ($.inArray($(id.property_list).val(), high_perf) == -1) {
        $(id.pathway_list + " option[value='Standard Target Pathway']").remove();
    } else {
        pathway_options = []
        var values = $(id.pathway_list + " option").map(function() {pathway_options.push(this.value);})
        if ($.inArray('Standard Target Pathway', pathway_options) == -1){
            $(id.pathway_list).append('<option>Standard Target Pathway</option>');
        }
    }

});

$(id.affordable_boolean).change(function(){
    //Alert 4 must be checked when either of two fields changes
    if ($(id.acp_list).val() != '' && $(id.property_list).val() != '')
        form_validator.element(id.acp_list);

    //affordable_list field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.affordable_list).show();
    } else {
        $(group.affordable_list).hide();
        $(id.affordable_list).val('');
    }
});

$(id.pathway_list).change(function(){
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.pathway_list).removeClass("error-okay");
    form_validator.element(id.pathway_list);

    //Alert 1 must be checked when either of two fields changes
    if ($(id.property_list).val() != '')
        form_validator.element(id.property_list);

    //acp_list field appears if "Pathway Selected" = "Alternative Compliance Pathway"
    if($(id.pathway_list).val() == "Alternative Compliance Pathway") {
        $("#ticket_submission_form > button").prop('disabled', true);
//        $(group.acp_list).show();
    } else {
        $("#ticket_submission_form > button").prop('disabled', false);
        $(group.acp_list).hide();
        $(id.acp_list).val('');
    }
});

