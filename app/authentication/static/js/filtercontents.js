$(document).ready(function () {
        var testpersonid = localStorage.getItem('personid');
        var testtypeid = localStorage.getItem('typeid');
        if ((testpersonid==null &&testtypeid==null )|| testpersonid== "All"  || testtypeid=="All"){
            $.ajax({
                    method :"GET",
                    url: "/api/v1/categories/",
                    cache: false,
                    dataType: "json",
                    success: function (data) {
                            for (index in data) {
                                $('#listcategories').append('<li ><a href="'+"?category="+data[index].id +'"+> '+data[index].name  +'</a></li>');

                            }

                    },
                    error: function (data) {
                        console.log(data.error);
                    }

                });
         }
        else if(testpersonid!=null)
        {
            $.ajax({
                    method :"GET",
                    url: "/api/v1/person/"+testpersonid+"/categories/",
                    cache: false,
                    dataType: "json",
                    success: function (data) {
                        for (index in data) {
                                $('#listcategories').append('<li {% if data[index].selected %} class="selected"{% endif %}><a href="'+"?category="+data[index].id +'"+> '+data[index].name  +'</a></li>');
                        }

                    },
                    error: function (data) {
                        console.log(data.error);
                    }

                });
            localStorage.removeItem('personid');
        }
        else if(testtypeid!=null)
        {
            $.ajax({
                    method :"GET",
                    url: "/api/v1/type/"+testtypeid+"/categories/",
                    cache: false,
                    dataType: "json",
                    success: function (data) {
                        for (index in data) {
                                $('#listcategories').append('<li {% if data[index].selected %} class="selected"{% endif %}><a href="'+"?category="+data[index].id +'"+> '+data[index].name  +'</a></li>');
                        }

                    },
                    error: function (data) {
                        console.log(data.error);
                    }

                });
            localStorage.removeItem('typeid');
        }
        localStorage.removeItem('personid');
        localStorage.removeItem('typeid');
    });

$(document).on('click', '.admin-filter-person', function (e) {
    var clickId = this.id;
    id = $(e.target).text();
    localStorage.setItem('personid', id);
})

$(document).on('click', '.admin-filter-type', function (e) {
    var clickId = this.id;
    id = $(e.target).text();
    localStorage.setItem('typeid', id);
})

